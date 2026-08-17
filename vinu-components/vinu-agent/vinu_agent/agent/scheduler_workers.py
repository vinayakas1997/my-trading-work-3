"""Scheduler-triggered real team invocation (Phase 9 scheduler-wiring,
New-talk-agents/new-thinking/new-restructure/phases/
phase-9-scheduler-wiring/). The one place a cron-style worker (not a chat
session) invokes a real LLM team deterministically -- same
`TeamManager(...).run(task)` pattern `submit_thesis_tool.py`'s
`_run_team` already uses for the human-thesis hand-off, built standalone
here since there's no active chat session's already-built tool registry
to reuse. `build_registry()`'s `session_id`/`session_service`/
`workflow_tracker` params are all optional (confirmed by reading
`tools/__init__.py` directly -- only injected into tools that declare the
matching attr), so a synthetic per-cycle session_id is enough; no real
Session/SessionStore row is created for this.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .notify_channels import HttpDiscordChannel, HttpTelegramChannel
from .planner_triage_hook import PlannerTriage
from .significance_triage import (
    ChannelTarget,
    deliver_flag,
    detect_large_funding_pattern,
    detect_repeated_rejection_pattern,
    detect_thesis_contradiction_pattern,
)
from .team import TeamManager

LOG = logging.getLogger(__name__)


def run_team_for_ticker(service: Any, team_name: str, task: str, *, session_id: str) -> dict[str, Any]:
    """Direct TeamManager construction+run, bypassing the orchestrator's
    own chat/tool-call turn entirely -- the caller already decided WHAT to
    run (deterministically, via a triage hook); this just runs it."""
    from ..tools import build_registry

    registry = build_registry(
        services_config=service.config.services,
        skills_loader=service._skills_loader,
        llm=service._llm,
        teams_dir=service.config.teams_dir,
        run_store=service._team_run_store,
        llm_call_store=service._llm_call_store,
        strategy_store=service._strategy_store,
        ticker_summary_store=service._ticker_summary_store,
        ticker_ledger_store=service._ticker_ledger_store,
        session_id=session_id,
        config=service.config,
    )
    team_dir = Path(service.config.teams_dir) / team_name
    manager = TeamManager(
        team_dir,
        full_registry=registry,
        llm=service._llm,
        skills_loader=service._skills_loader,
        run_store=service._team_run_store,
        llm_call_store=service._llm_call_store,
        strategy_store=service._strategy_store,
        ticker_summary_store=service._ticker_summary_store,
        ticker_ledger_store=service._ticker_ledger_store,
        triggered_by_session_id=session_id,
        services_config=service.config.services,
    )
    return manager.run(task)


def make_summary_agent_fn(service: Any):
    """RunLogTrigger.refresh_if_stale's `summary_agent_fn(ticker) ->
    (summary_text, meta)`. `angles_with_data`/`angle_count` come from a
    direct, deterministic `get_all_angles()` call -- never parsed from the
    LLM's prose -- same "traceable to real stored data, not invented"
    rule mermaid-explanation.md states as the Summary Agent's own defining
    characteristic.

    Note: the `screener` team's own result hook (`team.py`'s
    `_apply_team_result_hook`) already calls `write_ticker_summaries` on
    a completed run, so this ticker's summary row gets upserted twice per
    refresh -- once by that hook (multi-ticker, parsed from the response),
    once by `RunLogTrigger.refresh_if_stale` itself (single-ticker, the
    trigger's own source_run_id bookkeeping). Deliberately left
    un-deduplicated, same reasoning as Phase 5's debrief.py/
    feedback_loop.py overlap: both writes target the same real row with
    the same real data, last-write-wins is harmless, and de-duplicating
    across the hook/trigger boundary isn't worth the coupling it would add.
    """
    from ..tools.angles_tool import GetAllAnglesTool

    def _fn(ticker: str) -> tuple[str, dict[str, Any]]:
        angles_tool = GetAllAnglesTool()
        angles_tool._services_config = service.config.services
        angles_data = json.loads(angles_tool.execute(ticker=ticker))

        result = run_team_for_ticker(
            service, "screener", f"Ticker: {ticker}", session_id=f"summary-refresh-{ticker}",
        )
        summary_text = result.get("content", "") if result.get("status") == "completed" else ""
        return summary_text, {
            "angles_with_data": angles_data.get("angles_with_data", 0),
            "angle_count": angles_data.get("angle_count", 0),
        }

    return _fn


def discover_new_tickers(seed_tickers: list[str], ticker_summary_store: Any) -> list[str]:
    """Watchlist bootstrap gap, closed: every scheduled worker sources its
    watchlist from `TickerSummaryStore.list_summaries()`, which only ever
    contains tickers that already have a Summary Agent read on file --
    nothing previously added a genuinely NEW ticker to that store on its
    own (confirmed by reading `write_ticker_summaries`/`RunLogTrigger`/
    `planner-worker`/`significance-worker` directly: every writer is only
    ever invoked FOR a ticker already drawn from the same store, a closed
    loop). This is the one place a ticker can enter that loop: a static,
    operator-provided seed list (`VINU_AGENT_WATCHLIST_SEED_TICKERS`), not
    an invented external market-data discovery integration. Returns seed
    tickers not yet present in the store, de-duplicated, in seed order."""
    known = {s.ticker.upper() for s in ticker_summary_store.list_summaries()}
    seen: set[str] = set()
    new: list[str] = []
    for raw in seed_tickers:
        ticker = raw.strip().upper()
        if not ticker or ticker in known or ticker in seen:
            continue
        seen.add(ticker)
        new.append(ticker)
    return new


def bootstrap_new_tickers(service: Any, seed_tickers: list[str]) -> list[str]:
    """Runs the screener team once per not-yet-seen seed ticker -- the
    one-time cold start `write_ticker_summaries` (via `team.py`'s result
    hook) needs to upsert that ticker's first row into TickerSummaryStore,
    after which planner-worker/significance-worker's own
    list_summaries()-sourced cycles pick it up like any other ticker.
    Best-effort per ticker (same contract as every other scheduled-worker
    step): one ticker's screener run failing must not stop the others, and
    a ticker that fails here is simply retried on the next cycle (it's
    still "new" until a summary actually lands), not tracked as a
    permanent failure."""
    new_tickers = discover_new_tickers(seed_tickers, service.ticker_summary_store)
    bootstrapped: list[str] = []
    for ticker in new_tickers:
        try:
            run_team_for_ticker(
                service, "screener", f"Ticker: {ticker}", session_id=f"watchlist-bootstrap-{ticker}",
            )
            bootstrapped.append(ticker)
        except Exception:
            LOG.exception("watchlist bootstrap failed for %s, continuing", ticker)
    return bootstrapped


def build_channel_targets(config: Any) -> list[ChannelTarget]:
    """Each channel is independently gated on its own token+id being set
    -- Telegram and Discord can be turned on one at a time, and a future
    channel (e.g. WhatsApp) is one more independently-gated append here,
    never a redesign. An unconfigured channel is silently omitted, not an
    error -- same "skip, don't guess" fail-closed direction as every other
    cost-only gate in this build."""
    targets: list[ChannelTarget] = []
    if config.telegram_token and config.telegram_admin_chat_id:
        targets.append(ChannelTarget(HttpTelegramChannel(config.telegram_token), config.telegram_admin_chat_id))
    else:
        LOG.info("Telegram not configured (TELEGRAM_TOKEN / VINU_AGENT_TELEGRAM_ADMIN_CHAT_ID), skipping")
    if config.discord_token and config.discord_admin_channel_id:
        targets.append(ChannelTarget(HttpDiscordChannel(config.discord_token), config.discord_admin_channel_id))
    else:
        LOG.info("Discord not configured (DISCORD_TOKEN / VINU_AGENT_DISCORD_ADMIN_CHANNEL_ID), skipping")
    return targets


async def _run_detector_for_ticker(
    ticker: str, reason: str, detail_fn, detect_fn, *, flag_store: Any, targets: list[ChannelTarget],
) -> Any | None:
    try:
        hit = detect_fn(ticker)
    except Exception:
        LOG.exception("significance detection (%s) failed for %s, skipping", reason, ticker)
        return None
    if not hit:
        return None

    flag = flag_store.create_flag(ticker, reason, detail_fn(hit))
    if targets:
        await deliver_flag(flag, targets)
    else:
        LOG.warning("Significance flag %s created for %s but no channel is configured to deliver it", flag.flag_id, ticker)
    return flag


async def run_significance_cycle(
    tickers: list[str],
    ticker_ledger_store: Any,
    flag_store: Any,
    targets: list[ChannelTarget],
    *,
    funding_threshold: float,
) -> list[Any]:
    """One pass over the watchlist: detect, store, deliver, for all three
    named patterns (see significance_triage.py's module docstring for what
    each one actually means and where its threshold comes from).
    `funding_threshold` has no default -- callers pass
    `TradingMandate.load().max_order_value`, never a number invented here."""
    flags: list[Any] = []
    for ticker in tickers:
        flag = await _run_detector_for_ticker(
            ticker, "repeated_risk_gatekeeper_rejection",
            lambda hit: f"{hit['count']} REJECTED verdicts in the last {hit['window_hours']}h",
            lambda t: detect_repeated_rejection_pattern(t, ticker_ledger_store),
            flag_store=flag_store, targets=targets,
        )
        if flag:
            flags.append(flag)

        flag = await _run_detector_for_ticker(
            ticker, "large_funding_decision",
            lambda hit: f"funded ${hit['amount']:,.2f} (>= ${hit['threshold']:,.2f} threshold) in the last {hit['window_hours']}h",
            lambda t: detect_large_funding_pattern(t, ticker_ledger_store, threshold=funding_threshold),
            flag_store=flag_store, targets=targets,
        )
        if flag:
            flags.append(flag)

        flag = await _run_detector_for_ticker(
            ticker, "thesis_contradicting_close",
            lambda hit: f"{hit['count']} thesis-contradicting close(s) in the last {hit['window_hours']}h",
            lambda t: detect_thesis_contradiction_pattern(t, ticker_ledger_store),
            flag_store=flag_store, targets=targets,
        )
        if flag:
            flags.append(flag)

    return flags


def run_capital_allocator_cycle(service: Any, *, budget: float, cycle: int = 0) -> dict[str, Any]:
    """One capital-allocation pass over the whole PEND batch -- the
    scheduled caller shortcoming #1 was missing (an approved candidate
    could sit PEND indefinitely because nothing invoked the
    capital_allocator team on an interval). Collects every PEND artifact
    (risk_gatekeeper-approved, awaiting funding) in one shot, hands the
    full batch + the configured risk budget to the real capital_allocator
    team -- same `run_team_for_ticker(...)` pattern planner-worker uses
    for its research hand-off -- and reports what got funded. The team's
    own hook (agent/capital_allocator_hook.py) applies the PEND->ACTIVE /
    PENDBLOCK transitions from the manager's parsed final answer; nothing
    here mutates state. `budget` has no default -- callers pass the
    configured `capital_allocator_budget`, never a number invented here.

    Returns:
        {"status": "skipped", "reason": ..., "pend_candidates": 0} when
        the batch is empty (no LLM call -- nothing to fund), or
        {"status": "ok", "run_id", "pend_candidates", "funded": [...]}
        after a completed team run.
    """
    from vinu_research.models import ArtifactStatus

    pend = service._strategy_store.list_artifacts_by_statuses([ArtifactStatus.PEND])
    if not pend:
        return {
            "status": "skipped",
            "reason": "no PEND artifacts awaiting funding",
            "pend_candidates": 0,
        }

    artifact_ids = [a.artifact_id for a in pend]
    task = (
        "Run your capital-allocation cycle for the whole current PEND batch.\n"
        f"PEND artifact ids: {', '.join(artifact_ids)}\n"
        f"Total risk budget: ${budget:.2f}\n"
        "Follow your normal process: delegate to allocation_analyst, then "
        "emit your final JSON funding decision."
    )
    result = run_team_for_ticker(
        service, "capital_allocator", task, session_id=f"capital-allocator-{cycle}",
    )
    funded = [f for f in (result.get("artifact_id") or "").split(",") if f]
    return {
        "status": "ok",
        "run_id": result.get("run_id"),
        "pend_candidates": len(pend),
        "funded": funded,
    }


def hypothesis_reader_for(service: Any):
    """In-process first (`broker/research_link.py`'s
    `get_hypothesis_registry()`, confirmed real and live today, same
    pattern Phase 8's `trade_plan_calibration.py` already established) --
    converts `Hypothesis` dataclasses to the dict shape `PlannerTriage`/
    THGATE both already expect, matching `submit_thesis_tool.py`'s
    `_HttpHypothesisReader`'s own dict shape so Planner triage and Thesis
    Intake read prior hypotheses identically regardless of transport."""
    from ..broker.research_link import get_hypothesis_registry

    registry = get_hypothesis_registry()

    class _Reader:
        def query_by_symbol(self, ticker: str) -> list[dict[str, Any]]:
            return [
                {
                    "hypothesis_id": h.hypothesis_id, "thesis": h.thesis,
                    "status": h.status.value, "invalidation_reason": h.invalidation_reason,
                }
                for h in registry.query_by_symbol(ticker)
            ]

    return _Reader()


def make_planner_on_yes(service: Any, triage: PlannerTriage):
    """ChangeGate's `run_gate_cycle` `on_yes` callback -- the triage hook
    decides deterministically WHETHER and WHAT to propose; on a
    should_propose verdict, hands off to the real `research` team
    (`idea_generator`), exactly the same downstream loop Thesis Intake's
    own hand-off (`submit_thesis_tool.py`) already uses for human-
    submitted ideas."""

    def _on_yes(ticker: str, gate_result: Any) -> None:
        result = triage.check(ticker)
        if not result.should_propose:
            LOG.info("Planner triage skipped %s: %s", ticker, result.reason)
            return

        task = (
            f"Ticker: {ticker}\n"
            f"Use sweep recipe: {result.recipe_name}\n"
            f"Triage reasoning: {result.reason}\n"
        )
        if result.prior_rejections:
            task += (
                "\nPrior rejected hypotheses on this ticker -- do not "
                "blindly re-propose the same idea:\n"
                + "\n".join(f"- {r}" for r in result.prior_rejections)
            )

        handoff = run_team_for_ticker(service, "research", task, session_id=f"planner-{ticker}")
        triage.on_propose(ticker, result, ref_id=handoff.get("run_id", ""))

    return _on_yes
