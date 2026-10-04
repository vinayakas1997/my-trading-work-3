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
from datetime import datetime, timezone
from typing import Any

import httpx

from vinu_infra.pipeline_edge_recorder import record_edge
from vinu_live.config import LiveConfig
from vinu_live.live_decision import conditions, state_tracker
from vinu_live.live_decision.bars_client import fetch_recent_bars
from vinu_live.live_decision.detector import compute_live_snapshot, detect_move, feature_window_bars
from vinu_live.live_decision.position_rules import evaluate_position_rules
from vinu_live.live_decision.schema import LiveDecisionOpenPosition
from vinu_live.live_decision.storage import (
    LiveDecisionBackend,
    advance_cursor,
    close_position,
    count_unresolved_decision_attempts,
    get_cursor,
    get_stage_state,
    list_open_positions,
    list_snapshots,
    mark_position_reviewed,
    record_live_snapshot,
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
        self._novelty: dict[str, dict[str, Any]] = {}   # latest per-ticker novelty result (B1), when enabled
        self._last_close: dict[tuple[str, str], float] = {}   # (ticker, timeframe) -> close of the newest processed candle

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
        strategy_by_id = {s["name"]: s for s in strategies}

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
                closed_only=self._config.live_decision_closed_bars_only,
            )
            if latest.empty or "bar_ts" not in latest.columns:
                continue
            latest_bar_ts = int(latest["bar_ts"].iloc[-1])
            if cursor is not None and latest_bar_ts <= cursor.last_processed_bar_ts:
                continue  # no new candle for this pair this cycle

            warmup = await fetch_recent_bars(
                self._http, self._config.stock_price_api_url, ticker, timeframe,
                limit=feature_window_bars(self._config.live_decision_feature_window_bars),
                closed_only=self._config.live_decision_closed_bars_only,
            )
            if warmup.empty:
                continue
            self._remember_last_close(ticker, timeframe, warmup)
            snapshot = compute_live_snapshot(warmup)
            self._check_novelty(ticker, timeframe, snapshot)   # before recording, so the reference excludes this row

            # Present-data recording (missing-pieces-of-system/new-theory-
            # of-trading/system-wide-audit-and-design/
            # 02-open-questions-strategy-and-simulation.md item #5):
            # mirrors vinu-initial-analysis's RunLog, but for live/
            # present-moment computation -- one real, durable row every
            # time this pair's snapshot is freshly (re)computed, keyed on
            # wall-clock recency rather than a historical range. Recorded
            # once per (ticker, timeframe) group here, shared across every
            # strategy watching that pair, not once per strategy --
            # `angle_name="live_indicators"` names this specific
            # computation (point 3's detector output); a future writer
            # recording a different kind of live computation would use a
            # different angle_name against this same table.
            record_live_snapshot(
                self._backend, symbol=ticker, angle_name="live_indicators",
                granularity=timeframe, snapshot_data=snapshot,
            )

            # item #10 (system-wide-audit-and-design/
            # 02-open-questions-strategy-and-simulation.md): Track 2's move
            # check runs here, unconditionally, once per (ticker, timeframe)
            # group -- same reasoning as the snapshot recording just above.
            # If this only ran inside the per-strategy loop below, a real
            # move on a ticker with no must-condition currently firing
            # would never be checked at all, which is exactly the
            # "track2_only" blind spot this item exists to close.
            await self._detect_and_record_move(ticker, timeframe, latest_bar_ts, warmup, snapshot)

            for strat in watching_strategies:
                strategy_id = strat["name"]
                previous_state = get_stage_state(self._backend, ticker, strategy_id)
                previous_stage = previous_state.stage
                must_conditions = strat.get("must_conditions", [])
                new_state = state_tracker.evaluate_candle_close(
                    self._backend,
                    ticker=ticker,
                    strategy_id=strategy_id,
                    bar_ts=latest_bar_ts,
                    timeframe_seconds=timeframe_to_seconds(timeframe),
                    live_snapshot=snapshot,
                    must_conditions=must_conditions,
                    confirmation_conditions=strat.get("confirmation_conditions", []),
                    grace_window_bars=strat.get("grace_window_bars", 10),
                )
                events_fired += 1

                # The SignalEvidenceStore writer gap (found while building
                # item #10, system-wide-audit-and-design/
                # 02-open-questions-strategy-and-simulation.md): a fresh
                # trigger_id means a must-condition genuinely fired THIS
                # cycle -- not `previous_stage == "idle"` alone, since a
                # terminal-stage reset-then-refire can happen within one
                # call to evaluate_candle_close (state_tracker's own "Step
                # 5" comment), which would otherwise skip this guard.
                if new_state.trigger_id is not None and new_state.trigger_id != previous_state.trigger_id:
                    await self._record_signal_evidence_trigger(
                        ticker, must_conditions, new_state.trigger_id, latest_bar_ts, snapshot,
                    )

                # Point 5's trigger: only on the exact cycle a pair
                # FRESHLY reaches ready_to_execute -- not every cycle it
                # sits there, which state_tracker's own "do not
                # re-evaluate must-conditions while ready_to_execute"
                # rule (03-poller-and-state-schema.md Part B step 4)
                # already guards against corrupting, but this loop still
                # needs its own guard against re-calling the agent every
                # single poll while still awaiting mark_executed.
                if new_state.stage == "ready_to_execute":
                    if previous_stage != "ready_to_execute":
                        await self._trigger_live_decision(ticker, strategy_id, latest_bar_ts, new_state.trigger_id)
                    else:
                        # Still ready from an earlier candle, so the earlier
                        # call did not resolve it (a resolved call moves the
                        # pair to `executed`). Retry, bounded -- before this a
                        # failed call left the pair stuck here forever.
                        await self._retry_or_expire_unresolved(
                            ticker, strategy_id, latest_bar_ts, new_state.trigger_id,
                        )

            # logic-audit A3: rule-based stop / max-hold for positions already
            # open on this pair, checked on every new candle -- no LLM call.
            self._apply_position_rules(ticker, timeframe, latest_bar_ts, warmup, watching_strategies)

            advance_cursor(self._backend, ticker, timeframe, latest_bar_ts)

        positions_reviewed = await self._review_open_positions(strategy_by_id)

        return {
            "strategies_checked": len(strategies),
            "ticker_timeframe_pairs": len(groups),
            "candle_close_events": events_fired,
            "positions_reviewed": positions_reviewed,
        }

    def _apply_position_rules(
        self, ticker: str, timeframe: str, bar_ts: int, bars: Any,
        watching_strategies: list[dict[str, Any]],
    ) -> int:
        """Closes any open position on `ticker` whose strategy configured a
        stop (`live_decision_stop_pct`) or a max hold (`live_decision_max_hold_bars`)
        that the newest candle breaches. Same close mechanism as an agent EXIT
        (`close_position`), so the next scheduler cycle simply omits the weight
        and the existing not-targeted rule sells it. Recorded as a normal
        `EXIT` decision so history and the agent's anti-flip-flop context see it.
        Off for every strategy that sets neither field. Never raises: a rule
        failure must not stop the poll for other pairs."""
        closed = 0
        try:
            if bars is None or getattr(bars, "empty", True) or "close" not in bars.columns:
                return 0
            last_close = float(bars["close"].iloc[-1])
            by_id = {s["name"]: s for s in watching_strategies}
            for pos in list_open_positions(self._backend):
                if pos.ticker != ticker or pos.strategy_id not in by_id:
                    continue
                strat = by_id[pos.strategy_id]
                hit = evaluate_position_rules(
                    position_size=pos.position_size, entry_price=pos.entry_price,
                    last_close=last_close, opened_bar_ts=pos.opened_bar_ts, bar_ts=bar_ts,
                    timeframe_seconds=timeframe_to_seconds(timeframe),
                    stop_pct=float(strat.get("live_decision_stop_pct", 0.0) or 0.0),
                    max_hold_bars=int(strat.get("live_decision_max_hold_bars", 0) or 0),
                )
                configured = bool(float(strat.get("live_decision_stop_pct", 0.0) or 0.0) or int(strat.get("live_decision_max_hold_bars", 0) or 0))
                record_edge(
                    "strategy.stop_rules->live.poller", "received" if configured else "empty",
                    f"{pos.ticker}/{pos.strategy_id}: " + ("rules configured" if configured else "no stop / max-hold configured (off)"),
                    payload=strat,
                )
                if hit is None:
                    continue
                rule, detail = hit
                reasoning = f"rule_exit:{rule} -- {detail}"
                from vinu_live.live_decision.schema import LiveDecisionRecord
                from vinu_live.live_decision.storage import record_live_decision

                record_live_decision(self._backend, LiveDecisionRecord(
                    ticker=pos.ticker, strategy_id=pos.strategy_id, trigger_id=f"pos_{pos.id}",
                    bar_ts=bar_ts, decision="EXIT", precondition_held=None,
                    reasoning=reasoning, raw_content="",
                ))
                close_position(self._backend, pos.id, reason=reasoning, bar_ts=bar_ts, exit_price=last_close)
                LOG.warning("position rule EXIT for %s/%s (position %s): %s",
                            pos.ticker, pos.strategy_id, pos.id, reasoning)
                closed += 1
        except Exception as exc:  # noqa: BLE001 -- must not stop the poll
            LOG.warning("position rules failed for %s: %s", ticker, exc)
        return closed

    def _check_novelty(self, ticker: str, timeframe: str, snapshot: dict[str, Any]) -> None:
        """v2 B1 (opt-in, observe-only): compare this snapshot with the ticker's own recorded history."""
        if not self._config.live_decision_novelty_enabled or not snapshot:
            return
        try:
            from vinu_live.live_decision.novelty import novelty_ratio

            history = list_snapshots(
                self._backend, ticker, "live_indicators", limit=self._config.live_decision_novelty_reference_rows,
            )
            result = novelty_ratio(
                snapshot, [h.snapshot_data for h in history],
                min_reference=self._config.live_decision_novelty_min_reference,
                ratio_threshold=self._config.live_decision_novelty_ratio,
            )
            self._novelty[ticker] = result
            record_live_snapshot(self._backend, symbol=ticker, angle_name="live_novelty", granularity=timeframe,
                                 snapshot_data=result)
            if result["status"] != "ok":
                record_edge("live_decision.input_novelty->live.poller", "empty", f"{ticker}: {result.get('reason')}")
                return
            record_edge("live_decision.input_novelty->live.poller", "received", f"{ticker}: ratio {result['ratio']:.2f}", payload=result)
            if result["novelty_high"]:
                LOG.warning("input novelty HIGH for %s: ratio %.2f >= %.2f over %d snapshots -- this feature vector is "
                            "unlike its recent history", ticker, result["ratio"],
                            self._config.live_decision_novelty_ratio, result["n_reference"])
        except Exception as exc:                      # observe-only: never disturb the poll cycle
            LOG.warning("novelty check failed for %s: %s", ticker, exc)
            record_edge("live_decision.input_novelty->live.poller", "missing", f"{ticker}: {exc}")

    async def _review_open_positions(self, strategy_by_id: dict[str, Any]) -> int:
        """The exit-mechanism fix (missing-pieces-of-system/new-theory-
        of-trading/system-wide-audit-and-design/
        04-synthesis-built-vs-missing-2026-09-28.md): a live_decision-
        opened position previously had no way to ever close except the
        (now-fixed) accidental auto-close bug. This re-invokes
        live_decision_agent on a bar-count cadence for every currently
        open position, asking HOLD or EXIT -- reusing the same team/tool
        the entry decision already uses (05-deciding-agent-and-
        precondition-tracking.md's "reduce, don't rebuild" precedent),
        not a second agent stood up for this.

        Cadence is measured in real market bars via each position's own
        strategy timeframe (same bar_ts-based reasoning state_tracker's
        grace window already uses), not wall-clock time -- a strategy
        no longer enabled/found is left open and un-reviewed rather than
        guessed at; that is a real, separate design gap (a strategy
        removed out from under an open position), not silently handled
        here.
        """
        reviewed = 0
        for pos in list_open_positions(self._backend):
            strat = strategy_by_id.get(pos.strategy_id)
            if strat is None:
                continue
            timeframe = strat.get("schedule", "1d")
            cursor = get_cursor(self._backend, pos.ticker, timeframe)
            if cursor is None:
                continue
            last_reviewed = (
                pos.last_reviewed_bar_ts if pos.last_reviewed_bar_ts is not None
                else pos.opened_bar_ts
            )
            cadence_seconds = (
                self._config.live_decision_position_review_cadence_bars
                * timeframe_to_seconds(timeframe)
            )
            if cursor.last_processed_bar_ts - last_reviewed < cadence_seconds:
                continue
            await self._trigger_position_review(
                pos, cursor.last_processed_bar_ts, exit_price=self._last_close.get((pos.ticker, timeframe)),
            )
            reviewed += 1
        return reviewed

    def _remember_last_close(self, ticker: str, timeframe: str, bars: Any) -> None:
        """The close of the newest processed candle for this pair, kept so an exit decided later in the cycle
        (the agent's review) can record what the position was worth when it closed. Best-effort; never raises."""
        try:
            value = float(bars["close"].iloc[-1])
            if value > 0 and value == value and value != float("inf"):
                self._last_close[(ticker, timeframe)] = value
        except Exception:  # noqa: BLE001
            pass

    async def _trigger_position_review(
        self, pos: LiveDecisionOpenPosition, bar_ts: int, exit_price: float | None = None,
    ) -> None:
        """Calls the same `/agent/live-decision/run` route the entry
        trigger uses, with mode="review" so live_decision_agent's prompt
        asks HOLD/EXIT instead of EXECUTE/SKIP/EXTEND_GRACE_WINDOW.
        Every real outcome is durably recorded (same "record everything,
        even failures" rule `_trigger_live_decision` already established)
        under a synthetic `pos_<id>` trigger_id, since a review isn't
        tied to a fresh must-condition trigger the way an entry decision
        is.

        Only HOLD/EXIT actually advance `last_reviewed_bar_ts` -- an HTTP
        failure or an unrecognized answer leaves it unchanged so the next
        cycle retries immediately rather than silently waiting a full
        cadence again on a real infrastructure problem.
        """
        from vinu_live.live_decision.schema import LiveDecisionRecord
        from vinu_live.live_decision.storage import record_live_decision

        trigger_id = f"pos_{pos.id}"
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/live-decision/run",
                json={
                    "ticker": pos.ticker, "strategy_id": pos.strategy_id,
                    "mode": "review",
                    "position_context": {
                        "opened_at": pos.opened_at,
                        "opened_bar_ts": pos.opened_bar_ts,
                        "position_size": pos.position_size,
                    },
                },
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as exc:
            LOG.error(
                "position-review trigger failed for %s/%s (position %s) -- "
                "will retry next cycle: %s", pos.ticker, pos.strategy_id, pos.id, exc,
            )
            record_live_decision(self._backend, LiveDecisionRecord(
                ticker=pos.ticker, strategy_id=pos.strategy_id, trigger_id=trigger_id, bar_ts=bar_ts,
                decision="error", precondition_held=None,
                reasoning=f"HTTP call to /agent/live-decision/run (review) failed: {exc}",
                raw_content="",
            ))
            return

        decision = result.get("decision", "")
        reasoning = result.get("reasoning", "")

        record_live_decision(self._backend, LiveDecisionRecord(
            ticker=pos.ticker, strategy_id=pos.strategy_id, trigger_id=trigger_id, bar_ts=bar_ts,
            decision=decision or "unrecognized", precondition_held=result.get("precondition_held"),
            reasoning=reasoning, raw_content=result.get("content", ""),
        ))

        if decision == "EXIT":
            close_position(self._backend, pos.id, reason=reasoning, bar_ts=bar_ts, exit_price=exit_price)
            mark_position_reviewed(self._backend, pos.id, bar_ts)
            LOG.info("position-review EXIT for %s/%s (position %s): %s", pos.ticker, pos.strategy_id, pos.id, reasoning)
        elif decision == "HOLD":
            mark_position_reviewed(self._backend, pos.id, bar_ts)
            LOG.info("position-review HOLD for %s/%s (position %s): %s", pos.ticker, pos.strategy_id, pos.id, reasoning)
        else:
            LOG.error(
                "position-review for %s/%s (position %s) returned an unrecognized decision %r -- "
                "will retry next cycle", pos.ticker, pos.strategy_id, pos.id, decision,
            )

    async def _retry_or_expire_unresolved(
        self, ticker: str, strategy_id: str, bar_ts: int, trigger_id: str | None,
    ) -> None:
        """A ready_to_execute pair whose live-decision call has not produced a
        usable verdict. Under the attempt limit: call again (one attempt per
        candle close is a natural backoff). At the limit: expire the trigger
        (terminal for this trigger, so the pair resets to idle and can fire
        again), record why, and notify once. A limit of 0 keeps the old
        never-retry behavior; a missing trigger_id cannot be counted, so it is left alone."""
        max_attempts = self._config.live_decision_max_trigger_attempts
        if max_attempts <= 0 or trigger_id is None:
            return
        attempts = count_unresolved_decision_attempts(self._backend, ticker, strategy_id, trigger_id)
        if attempts < max_attempts:
            LOG.warning(
                "live-decision for %s/%s still unresolved after %d attempt(s) -- retrying (limit %d)",
                ticker, strategy_id, attempts, max_attempts,
            )
            await self._trigger_live_decision(ticker, strategy_id, bar_ts, trigger_id)
            return

        from vinu_live.live_decision.schema import LiveDecisionRecord
        from vinu_live.live_decision.storage import record_live_decision

        reasoning = (
            f"gave up after {attempts} unresolved live-decision attempts "
            f"(limit {max_attempts}); trigger expired so the pair can fire again"
        )
        state_tracker.mark_expired(self._backend, ticker, strategy_id, bar_ts)
        record_live_decision(self._backend, LiveDecisionRecord(
            ticker=ticker, strategy_id=strategy_id, trigger_id=trigger_id, bar_ts=bar_ts,
            decision="error", precondition_held=None, reasoning=reasoning, raw_content="",
        ))
        LOG.error("live-decision %s/%s: %s", ticker, strategy_id, reasoning)
        await self._notify_stuck_decision(ticker, strategy_id, trigger_id, reasoning)

    async def _notify_stuck_decision(
        self, ticker: str, strategy_id: str, trigger_id: str | None, reasoning: str,
    ) -> None:
        """Best-effort push through the shared notify front door (same route and
        reuse-by-action pattern the scheduler's target-weight-drift alert uses).
        Edge-triggered by construction: the trigger is expired right before this,
        so it is called once per stuck trigger. A failure never affects the loop."""
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/notify/reconciliation-drift",
                json={
                    "symbol": f"{ticker}/{strategy_id}",
                    "action": "live_decision_stuck",
                    "detail": f"trigger {trigger_id}: {reasoning}",
                },
            )
            resp.raise_for_status()
            record_edge("live_decision.stuck_trigger->agent.notify", "received", f"{ticker}/{strategy_id}")
        except Exception as exc:  # noqa: BLE001
            LOG.warning("could not send stuck-decision notification for %s/%s: %s", ticker, strategy_id, exc)
            record_edge("live_decision.stuck_trigger->agent.notify", "missing", f"{ticker}/{strategy_id}: {exc}")

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

        payload: dict[str, Any] = {"ticker": ticker, "strategy_id": strategy_id, "trigger_id": trigger_id}
        novelty = self._novelty.get(ticker)
        if novelty and novelty.get("novelty_high"):
            payload["novelty"] = novelty
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/live-decision/run",
                json=payload,
            )
            resp.raise_for_status()
            result = resp.json()
        except Exception as exc:
            LOG.error(
                "live-decision trigger failed for %s/%s -- pair stays ready_to_execute and is "
                "retried on later candles (bounded by live_decision_max_trigger_attempts): %s",
                ticker, strategy_id, exc,
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
            # Point 6's write-back (reverse-engineering/
            # 05-deciding-agent-and-precondition-tracking.md Part C):
            # EXECUTE and SKIP are both a real check against real
            # evidence -- being checked and failing (SKIP) still counts
            # as tested. EXTEND_GRACE_WINDOW/error/unrecognized do not
            # (no real verdict was reached).
            await self._record_precondition_check(strategy_id, precondition_held)
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
                "pair stays ready_to_execute and is retried on later candles (bounded)",
                ticker, strategy_id, decision,
            )

    async def _record_precondition_check(self, strategy_id: str, precondition_held: bool | None) -> None:
        """Point 6's write-back call (reverse-engineering/
        05-deciding-agent-and-precondition-tracking.md Part C) --
        best-effort, same posture as every other side-write in this
        codebase (e.g. MaturityConsultationStore's own recording calls):
        a failure here must never break the live-decision loop itself,
        since this only updates a strategy's own `precondition.tested`
        visibility, not anything the trading loop depends on reading
        back."""
        try:
            resp = await self._http.post(
                f"{self._config.strategy_api_url}/strategy/strategies/{strategy_id}/precondition-check",
                json={"precondition_held": precondition_held},
            )
            resp.raise_for_status()
        except Exception as exc:
            LOG.warning(
                "could not record precondition check for strategy %s: %s", strategy_id, exc,
            )

    async def _detect_and_record_move(
        self, ticker: str, timeframe: str, bar_ts: int, bars: Any, snapshot: dict[str, Any],
    ) -> None:
        """item #10's Track 2 writer -- best-effort, same posture as
        `_record_precondition_check`: a failure here must never break the
        candle-close loop itself, since nothing the trading loop depends
        on reads this back. Only posts when `detect_move()` actually
        found a real move (`move_detected=True`) -- `None` (not enough
        history yet) and `move_detected=False` both mean "nothing to
        record," matching `MoveEvidenceStore`'s own "real events only"
        discipline."""
        move = detect_move(bars, snapshot)
        if move is None or not move["move_detected"]:
            return
        try:
            resp = await self._http.post(
                f"{self._config.research_api_url}/research/move-evidence/{ticker}",
                json={
                    "bar_ts": bar_ts,
                    "window_seconds": timeframe_to_seconds(timeframe),
                    "granularity": timeframe,
                    "atr": move["atr"],
                    "price_move": move["price_move"],
                    "move_threshold": move["threshold"],
                    "direction": move["direction"],
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            LOG.warning("could not record move event for %s/%s: %s", ticker, timeframe, exc)

    async def _record_signal_evidence_trigger(
        self,
        ticker: str,
        must_conditions: list[dict[str, Any]],
        trigger_id: str,
        bar_ts: int,
        snapshot: dict[str, Any],
    ) -> None:
        """The SignalEvidenceStore writer gap: `SignalEvidenceStore` (Phase
        2, vinu-research) has always had its store and route, but nothing
        in this codebase ever called `POST /research/signal-evidence/
        trigger` in production -- only a read-only agent tool referenced
        it (confirmed by grep while building item #10). This is that
        writer, called exactly once per real must-condition firing (see
        this method's own call site's trigger_id-changed guard).

        Best-effort, same posture as `_detect_and_record_move`/
        `_record_precondition_check`: a failure here must never break the
        candle-close loop, since nothing the trading loop depends on
        reads this back."""
        if not must_conditions:
            return
        condition_names = [conditions.condition_name(c) for c in must_conditions]
        trigger_time = datetime.fromtimestamp(bar_ts, tz=timezone.utc).isoformat()
        try:
            resp = await self._http.post(
                f"{self._config.research_api_url}/research/signal-evidence/trigger",
                json={
                    "trigger_id": trigger_id,
                    "symbol": ticker,
                    "trigger_time": trigger_time,
                    "must_condition": condition_names,
                    "indicators": snapshot,
                },
            )
            resp.raise_for_status()
        except Exception as exc:
            LOG.warning("could not record signal-evidence trigger for %s: %s", ticker, exc)
