"""Turns capital_allocator's completed funding decision into real status
transitions: every candidate the manager reported as funded moves
PEND -> ACTIVE via SqliteStrategyStore.mark_active() (Phase 2, New-talk-
agents/new-thinking/new-restructure/phases/phase-2-funding-mechanics/),
UNLESS the Kill Switch is engaged for that candidate's scope (Phase 3,
.../phase-3-kill-switch/), in which case it goes to PENDBLOCK instead --
funding was decided, execution is held. The kill-switch check happens
here, immediately before mark_active, wrapped in kill_switch.py's
kill_switch_lock() (added when this race was closed -- see
phase-3-kill-switch/04-implement-test.md's follow-up note) so
halt_trading() genuinely cannot complete while this check-then-act
section is mid-flight, not just "minimized" by keeping the two calls
adjacent. Never an agent tool (pillar 8) -- called from TeamManager.run()
after the manager's final answer is parsed, same shape as
risk_gatekeeper_hook.py and research_artifact_writer.py.
ComputeAllocationCandidatesTool (allocation_tool.py) only ever computes
the decision; this is the one place it's actually applied.

Also applies the manager's optional "unwind" list -- the rebalancer role
(mermaid-explanation.md section 5) named but never built until now. Each
entry is a REQUEST, never a direct action: gated by rebalance_guard.
check_rebalance_allowed (fail-closed to the kill switch, same direction
as funding above), then POSTed to vinu-live's rebalance-request intake
(server/app.py's /live/trade-plan/rebalance-request, Phase 5's
TradePlanOrchestrator.submit_rebalance_request) -- vinu-live's own
TradePlanOrchestrator decides on its next real cycle whether to actually
honor it, exactly as rebalance_guard.py's own docstring requires ("the
rebalancer never closes a position itself").
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

LOG = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)
_DEFAULT_VINU_LIVE_URL = "http://localhost:8091"


def _is_halted(scope: str) -> bool:
    """Fail-closed: on ANY uncertainty, assume halted. This is the one
    check in the whole design where the wrong default risks real money
    moving when it shouldn't (02-guard-rail.md) -- the other two
    fail-closed defaults in this codebase (Phase 0's RunLog trigger and
    change-gate) point in opposite directions from each other and from
    this one, deliberately, based on what's actually at risk in each
    case. In-process call (this hook runs inside the same agent-api
    process/container routes_broker.py's /broker/status reads from), not
    an HTTP round-trip to itself."""
    try:
        from ..broker.kill_switch import is_trading_halted
        return is_trading_halted(scope=scope)
    except Exception:
        LOG.exception("kill switch check failed for scope %r, defaulting to halted", scope)
        return True


def _extract_json_block(content: str) -> Optional[dict]:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _request_unwind(
    entry: dict, *, strategy_store: Any, ticker_ledger_store: Any, services_config: dict,
) -> None:
    """One "unwind" entry from the manager's final answer -> one REQUEST to
    vinu-live, never a direct action (see module docstring). Best-effort:
    any failure here is logged and swallowed, matching every other write
    in this hook -- a rebalance request is advisory, never on the critical
    funding path."""
    artifact_id = str(entry.get("artifact_id", "")).strip()
    if not artifact_id:
        return
    reason = str(entry.get("reason", "")).strip() or "capital_allocator requested unwind"

    try:
        artifact = strategy_store.get_artifact(artifact_id)
    except Exception:
        LOG.exception("failed to re-fetch %s for unwind request, continuing without it", artifact_id)
        return
    if artifact is None:
        return

    from vinu_research.models import ArtifactStatus

    if artifact.status != ArtifactStatus.ACTIVE:
        LOG.warning(
            "capital_allocator requested unwind of %s but it is not ACTIVE (status=%s), skipping",
            artifact_id, artifact.status.value,
        )
        return
    ticker = artifact.universe[0] if artifact.universe else ""
    if not ticker:
        return

    from .rebalance_guard import check_rebalance_allowed

    if not check_rebalance_allowed(ticker):
        if ticker_ledger_store is not None:
            try:
                ticker_ledger_store.add_event(
                    ticker=ticker, stage="capital_allocator", event_type="rebalance_blocked",
                    text=f"unwind requested for {artifact_id} but blocked (kill switch engaged for scope={ticker!r})",
                    ref_id=artifact_id, source="watchlist",
                )
            except Exception:
                LOG.exception("failed to write TickerLedger row for %s rebalance_blocked, continuing without it", artifact_id)
        return

    vinu_live_url = (services_config or {}).get("vinu_live", _DEFAULT_VINU_LIVE_URL)
    try:
        import httpx

        resp = httpx.post(
            f"{vinu_live_url}/live/trade-plan/rebalance-request",
            json={"symbol": ticker, "reason": reason},
            timeout=15,
        )
        resp.raise_for_status()
        event_type, text = "rebalance_requested", f"unwind requested for {artifact_id}: {reason}"
    except Exception as exc:
        LOG.warning("failed to submit rebalance request for %s to vinu-live: %s", artifact_id, exc)
        event_type, text = "rebalance_request_failed", f"unwind requested for {artifact_id} but vinu-live unreachable: {exc}"

    if ticker_ledger_store is not None:
        try:
            ticker_ledger_store.add_event(
                ticker=ticker, stage="capital_allocator", event_type=event_type,
                text=text, ref_id=artifact_id, source="watchlist",
            )
        except Exception:
            LOG.exception("failed to write TickerLedger row for %s %s, continuing without it", artifact_id, event_type)


def apply_capital_allocator_decision(
    content: str, *, strategy_store: Any, ticker_ledger_store: Any = None, services_config: dict | None = None,
) -> Optional[str]:
    """Best-effort: any failure here is logged and swallowed, never raised
    (same contract as risk_gatekeeper_hook.py). Returns a comma-joined list
    of funded artifact_ids for traceability (team_runs.related_artifact_id),
    or None if nothing was funded/parseable.
    """
    try:
        data = _extract_json_block(content)
        if not data:
            return None
        candidates = data.get("candidates") or []
        unwind_requests = data.get("unwind") or []
    except Exception:
        LOG.exception("failed to parse capital_allocator decision, continuing without it")
        return None

    for entry in unwind_requests:
        if not isinstance(entry, dict):
            continue
        try:
            _request_unwind(
                entry, strategy_store=strategy_store, ticker_ledger_store=ticker_ledger_store,
                services_config=services_config or {},
            )
        except Exception:
            LOG.exception("unwind request handling failed for %r, continuing without it", entry.get("artifact_id"))

    funded_ids: list[str] = []
    for c in candidates:
        if not isinstance(c, dict) or not c.get("funded"):
            continue
        artifact_id = str(c.get("artifact_id", "")).strip()
        if not artifact_id:
            continue
        amount = c.get("amount", 0.0)

        try:
            fresh = strategy_store.get_artifact(artifact_id)
        except Exception:
            LOG.exception("failed to re-fetch %s before funding, continuing without it", artifact_id)
            continue
        if fresh is None:
            continue
        ticker = fresh.universe[0] if fresh.universe else ""

        from ..broker.kill_switch import kill_switch_lock

        # Kill-switch check + the transition it gates are both inside this
        # lock -- halt_trading() (kill_switch.py) acquires the same lock,
        # so a halt issued mid-critical-section either lands before this
        # block starts or after it finishes, never in between.
        with kill_switch_lock():
            if _is_halted(ticker):
                try:
                    artifact = strategy_store.mark_pendblock(artifact_id)
                except Exception:
                    LOG.exception(
                        "failed to mark %s PENDBLOCK while kill switch engaged, continuing without it",
                        artifact_id,
                    )
                    continue
                if ticker_ledger_store is not None and ticker:
                    try:
                        ticker_ledger_store.add_event(
                            ticker=ticker, stage="capital_allocator", event_type="PENDBLOCK",
                            text=f"funding decided (amount={amount}) but Kill Switch engaged for scope={ticker!r}",
                            ref_id=artifact_id, source="watchlist",
                        )
                    except Exception:
                        LOG.exception(
                            "failed to write TickerLedger row for %s PENDBLOCK transition, continuing without it",
                            artifact_id,
                        )
                continue

            try:
                artifact = strategy_store.mark_active(artifact_id)
            except Exception:
                LOG.exception(
                    "failed to mark %s ACTIVE after capital_allocator funded it, continuing without it",
                    artifact_id,
                )
                continue

        funded_ids.append(artifact_id)

        if ticker_ledger_store is not None:
            try:
                ticker = artifact.universe[0] if artifact.universe else ""
                if ticker:
                    ticker_ledger_store.add_event(
                        ticker=ticker,
                        stage="capital_allocator",
                        event_type="funded",
                        text=f"capital_allocator funded and activated, amount={amount}",
                        ref_id=artifact_id,
                        source="watchlist",
                    )
            except Exception:
                LOG.exception(
                    "failed to write TickerLedger row for %s funded transition, continuing without it",
                    artifact_id,
                )

    return ",".join(funded_ids) if funded_ids else None
