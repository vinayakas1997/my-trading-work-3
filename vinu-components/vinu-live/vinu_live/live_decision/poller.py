"""Point 2: the candle-close poller.

Data-based watermark, not a time-based cron (see 03-poller-and-state-
schema.md Part A for why: a clock-based fire would misfire across
weekends/holidays/vendor delays). One fetch per (ticker, timeframe),
shared across every strategy watching that pair -- not one fetch per
strategy, avoiding the "no caching, re-fetch per caller" pattern already
flagged three times elsewhere in this design series (items #11.4, #13.4,
#21).

Same `while True: cycle(); sleep(interval)` shape as every other worker
in vinu-live (scheduler.py, feedback_loop.py, shadow_evaluator.py).
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from vinu_live.config import LiveConfig
from vinu_live.live_decision import state_tracker
from vinu_live.live_decision.bars_client import fetch_recent_bars
from vinu_live.live_decision.detector import compute_live_snapshot, min_warmup_bars
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    advance_cursor,
    get_cursor,
    get_stage_state,
)

LOG = logging.getLogger(__name__)

_TIMEFRAME_SECONDS: dict[str, int] = {
    "1m": 60, "5m": 300, "15m": 900, "30m": 1800,
    "1h": 3600, "4h": 14400, "1d": 86400, "daily": 86400,
}


def timeframe_to_seconds(timeframe: str) -> int:
    seconds = _TIMEFRAME_SECONDS.get(timeframe)
    if seconds is None:
        LOG.warning("Unknown timeframe %r, defaulting to 1d", timeframe)
        return 86400
    return seconds


class CandleClosePoller:
    def __init__(self, config: LiveConfig | None = None, backend: LiveDecisionBackend | None = None) -> None:
        self._config = config or LiveConfig.from_env()
        self._backend = backend or LiveDecisionBackend(str(self._config.data_root / "live_decision.db"))
        try:
            from vinu_infra.auth import internal_auth_headers
            headers = internal_auth_headers() or None
        except Exception:
            headers = None
        self._http = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def close(self) -> None:
        await self._http.aclose()
        self._backend.close()

    async def _fetch_active_strategies(self) -> list[dict[str, Any]]:
        """Every enabled strategy's full definition (schedule, resolved
        universe, must_conditions, confirmation_conditions,
        grace_window_bars) -- two calls (list then get-per-name) since
        `/strategy/strategies` only returns name/description/schedule/
        enabled (vinu_strategy/storage/meta.py::get_registered_strategies),
        not the full config `/strategy/strategies/{name}` returns."""
        try:
            resp = await self._http.get(f"{self._config.strategy_api_url}/strategy/strategies")
            resp.raise_for_status()
            summaries = resp.json()
        except Exception as exc:
            LOG.warning("Could not list strategies: %s", exc)
            return []

        strategies: list[dict[str, Any]] = []
        for s in summaries:
            if not s.get("enabled", True):
                continue
            try:
                resp = await self._http.get(
                    f"{self._config.strategy_api_url}/strategy/strategies/{s['name']}",
                )
                resp.raise_for_status()
                strategies.append(resp.json())
            except Exception as exc:
                LOG.warning("Could not fetch strategy %s: %s", s.get("name"), exc)
        return strategies

    async def cycle(self) -> dict[str, Any]:
        strategies = await self._fetch_active_strategies()

        # Group by (ticker, timeframe) so every strategy sharing a pair
        # gets exactly one bar fetch this cycle, not one per strategy.
        groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
        for strat in strategies:
            timeframe = strat.get("schedule", "1d")
            for ticker in strat.get("universe", []):
                groups.setdefault((ticker, timeframe), []).append(strat)

        events_fired = 0
        for (ticker, timeframe), watching_strategies in groups.items():
            cursor = get_cursor(self._backend, ticker, timeframe)
            latest = await fetch_recent_bars(
                self._http, self._config.stock_price_api_url, ticker, timeframe, limit=2,
            )
            if latest.empty or "bar_ts" not in latest.columns:
                continue
            latest_bar_ts = int(latest["bar_ts"].iloc[-1])
            if cursor is not None and latest_bar_ts <= cursor.last_processed_bar_ts:
                continue  # no new candle for this pair this cycle

            warmup = await fetch_recent_bars(
                self._http, self._config.stock_price_api_url, ticker, timeframe,
                limit=min_warmup_bars(),
            )
            if warmup.empty:
                continue
            snapshot = compute_live_snapshot(warmup)

            for strat in watching_strategies:
                strategy_id = strat["name"]
                previous_stage = get_stage_state(self._backend, ticker, strategy_id).stage
                new_state = state_tracker.evaluate_candle_close(
                    self._backend,
                    ticker=ticker,
                    strategy_id=strategy_id,
                    bar_ts=latest_bar_ts,
                    timeframe_seconds=timeframe_to_seconds(timeframe),
                    live_snapshot=snapshot,
                    must_conditions=strat.get("must_conditions", []),
                    confirmation_conditions=strat.get("confirmation_conditions", []),
                    grace_window_bars=strat.get("grace_window_bars", 10),
                )
                events_fired += 1

                # Point 5's trigger: only on the exact cycle a pair
                # FRESHLY reaches ready_to_execute -- not every cycle it
                # sits there, which state_tracker's own "do not
                # re-evaluate must-conditions while ready_to_execute"
                # rule (03-poller-and-state-schema.md Part B step 4)
                # already guards against corrupting, but this loop still
                # needs its own guard against re-calling the agent every
                # single poll while still awaiting mark_executed.
                if new_state.stage == "ready_to_execute" and previous_stage != "ready_to_execute":
                    await self._trigger_live_decision(ticker, strategy_id, latest_bar_ts, new_state.trigger_id)

            advance_cursor(self._backend, ticker, timeframe, latest_bar_ts)

        return {
            "strategies_checked": len(strategies),
            "ticker_timeframe_pairs": len(groups),
            "candle_close_events": events_fired,
        }

    async def _trigger_live_decision(
        self, ticker: str, strategy_id: str, bar_ts: int, trigger_id: str | None,
    ) -> None:
        """Point 5's trigger (reverse-engineering/
        06-execution-handoff-and-architecture.md, resolved): calls
        vinu-agent's new /agent/live-decision/run route, which runs the
        live_decision team using the already-running AgentService's own
        shared LLM/stores (session/service.py::run_team_once) --
        blocking, not fire-and-forget, since the resulting decision has
        to actually resolve this trigger's lifecycle (mark_executed)
        before the next candle-close for this pair should be considered.
        A failure here is logged AND recorded, not just raised -- one
        strategy's decision call failing must not crash the whole poll
        cycle for every other (ticker, timeframe) pair still being
        processed, but the failure itself is still queryable evidence
        (same "record everything, even failures" rule item #21.3
        already established), not silently swallowed.

        Every real outcome (EXECUTE, SKIP, EXTEND_GRACE_WINDOW, a call
        that failed outright, or one that came back with something
        unrecognized) gets a durable LiveDecisionRecord row -- this was
        previously only a LOG line, discarding the agent's actual
        evidence-grounded reasoning the moment the process log rotated.
        """
        from vinu_live.live_decision.schema import LiveDecisionRecord
        from vinu_live.live_decision.storage import record_live_decision

        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/live-decision/run",
                json={"ticker": ticker, "strategy_id": strategy_id, "trigger_id": trigger_id},
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as exc:
            LOG.error(
                "live-decision trigger failed for %s/%s -- pair stays ready_to_execute, "
                "will retry next cycle: %s", ticker, strategy_id, exc,
            )
            record_live_decision(self._backend, LiveDecisionRecord(
                ticker=ticker, strategy_id=strategy_id, trigger_id=trigger_id, bar_ts=bar_ts,
                decision="error", precondition_held=None,
                reasoning=f"HTTP call to /agent/live-decision/run failed: {exc}",
                raw_content="",
            ))
            return

        decision = result.get("decision", "")
        reasoning = result.get("reasoning", "")
        precondition_held = result.get("precondition_held")
        raw_content = result.get("content", "")

        record_live_decision(self._backend, LiveDecisionRecord(
            ticker=ticker, strategy_id=strategy_id, trigger_id=trigger_id, bar_ts=bar_ts,
            decision=decision or "unrecognized", precondition_held=precondition_held,
            reasoning=reasoning, raw_content=raw_content,
        ))

        if decision in ("EXECUTE", "SKIP"):
            reason = "agent_executed" if decision == "EXECUTE" else "agent_skipped"
            state_tracker.mark_executed(self._backend, ticker, strategy_id, bar_ts, reason=reason)
            LOG.info("live-decision %s for %s/%s: %s", decision, ticker, strategy_id, reasoning)
        elif decision == "EXTEND_GRACE_WINDOW":
            # Rare per live_decision_agent's own prompt (only applies to
            # fired_awaiting_confirmation, and this trigger only ever
            # fires on ready_to_execute) -- recorded above, but not
            # acted on, since there is no real mechanism for it yet at
            # this stage.
            LOG.warning(
                "live-decision returned EXTEND_GRACE_WINDOW for %s/%s on a "
                "ready_to_execute pair -- no-op, staying ready_to_execute", ticker, strategy_id,
            )
        else:
            LOG.error(
                "live-decision for %s/%s returned an unrecognized decision %r -- "
                "pair stays ready_to_execute, will retry next cycle", ticker, strategy_id, decision,
            )
