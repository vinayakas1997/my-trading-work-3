"""Phase 7: writes Phase 6's realized trade outcomes back into Phase 2's personality stats and
Phase 4's calibration tracking, and populates vinu-initial-analysis's `pnl_attribution` angle.

Lives in vinu-live (not vinu-research or vinu-initial-analysis) because it's the one holding
the source-of-truth closed-position data -- the same shape of job `shadow_evaluator.py` already
does (poll local/owned state, push updates to other services over HTTP). This is explicitly
*not* a live re-decision: every write here is consumed at the next research cycle or the next
`approve_trade_plan` call, never fed back into `TradePlanOrchestrator` or any in-trade action --
this module has no dependency on `trade_plan/orchestrator.py`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from vinu_live.book.positions import BookBackend, init_book, list_closed_positions, mark_feedback_processed
from vinu_live.config import LiveConfig, load_config

LOG = logging.getLogger(__name__)

_PERSONALITY_ANGLES = "shock_personality,shock_clustering"


def _realized_return_pct(position: dict[str, Any]) -> float:
    """The underlying's realized price return -- what a forecast's direction/magnitude is
    actually about, not the position's dollar PnL (which position sizing/commission affect).
    Not sign-flipped by side: a short position that profited from a price decline still
    reports a negative return here, which `compute_directional_error` correctly scores as a
    match for a "short" forecast.
    """
    avg_entry = float(position.get("avg_entry", 0.0) or 0.0)
    close_price = position.get("close_price")
    if avg_entry <= 0 or close_price is None:
        return 0.0
    return (float(close_price) - avg_entry) / avg_entry


class FeedbackLoopWorker:
    def __init__(self, config: LiveConfig | None = None, book: BookBackend | None = None) -> None:
        self._config = config or load_config()
        self._book = book or init_book(str(self._config.data_root / "trade_plan_book.db"))
        self._http = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self._http.aclose()
        self._book.close()

    async def cycle(self) -> dict[str, Any]:
        cycle_id = f"feedback_cycle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S%f')}"
        LOG.info("[%s] Starting feedback cycle", cycle_id)

        result: dict[str, Any] = {
            "cycle_id": cycle_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "processed": [],
        }

        try:
            closed = list_closed_positions(self._book, unprocessed_only=True)
            if not closed:
                result["status"] = "skipped_no_unprocessed_positions"
                return result

            processed = []
            for position in closed:
                processed.append(await self._process_closed_position(position))
            result["processed"] = processed

        except Exception as e:
            LOG.error("[%s] Feedback cycle failed: %s", cycle_id, e)
            result["status"] = "failed"
            result["error"] = str(e)

        return result

    async def _process_closed_position(self, position: dict[str, Any]) -> dict[str, Any]:
        position_id = position["position_id"]
        symbol = position["symbol"]
        artifact_id = position.get("artifact_id", "")
        realized_return_pct = _realized_return_pct(position)

        calibration_ok = await self._record_calibration_outcome(artifact_id, realized_return_pct)
        pnl_attribution_ok = await self._push_pnl_attribution(symbol, position)
        personality_ok = await self._refresh_personality_stats(symbol)

        # The real bookkeeping action (never reprocess this close) happens
        # first, same "persist before writing evidence" ordering
        # broker/debrief.py already uses -- see that module's docstring.
        mark_feedback_processed(self._book, position_id)

        # Phase 5 (New-talk-agents/new-thinking/new-restructure/phases/
        # phase-5-monitor-extend/): the two writes feedback_loop.py never
        # made before this phase. Both best-effort/never-raising, same
        # shape as the three calls above -- a failure here must never
        # reverse or re-open the position close that already happened.
        hypothesis_ok = await self._record_hypothesis_evidence(symbol, artifact_id, realized_return_pct)
        ticker_ledger_ok = await self._write_ticker_ledger_closeout(symbol, artifact_id, realized_return_pct)

        return {
            "position_id": position_id,
            "symbol": symbol,
            "artifact_id": artifact_id,
            "realized_return_pct": realized_return_pct,
            "calibration_recorded": calibration_ok,
            "pnl_attribution_recorded": pnl_attribution_ok,
            "personality_stats_refreshed": personality_ok,
            "hypothesis_evidence_recorded": hypothesis_ok,
            "ticker_ledger_recorded": ticker_ledger_ok,
        }

    async def _record_calibration_outcome(self, artifact_id: str, realized_return_pct: float) -> bool:
        if not artifact_id:
            LOG.info("Closed position has no artifact_id -- skipping calibration write-back")
            return False
        try:
            resp = await self._http.post(
                f"{self._config.research_api_url}/research/trade-plan/{artifact_id}/record-outcome",
                json={"actual_return_pct": realized_return_pct},
            )
            return resp.status_code == 200
        except Exception as e:
            LOG.warning("Failed to record calibration outcome for %s: %s", artifact_id, e)
            return False

    async def _push_pnl_attribution(self, symbol: str, position: dict[str, Any]) -> bool:
        try:
            resp = await self._http.post(
                f"{self._config.initial_analysis_api_url}/analysis/pnl-attribution/{symbol}/record",
                json={"closed_positions": [position]},
            )
            return resp.status_code == 200
        except Exception as e:
            LOG.warning("Failed to push pnl_attribution for %s: %s", symbol, e)
            return False

    async def _record_hypothesis_evidence(
        self, symbol: str, artifact_id: str, realized_return_pct: float,
    ) -> bool:
        """The write feedback_loop.py never made before Phase 5: a closed
        position's outcome reaches HypothesisRegistry, which the
        Planner's mandatory pre-proposal consult reads (New-talk-agents/
        new-thinking/new-restructure/phases/phase-5-monitor-extend/).

        Uses `metric="realized_return_pct"`, distinct from vinu-agent's
        own independent debrief.py detector (`metric="realized_pnl"`, a
        dollar amount, triggered by a different signal -- Alpaca fill
        replay during an active chat session, not this worker's own book).
        The two detectors can both fire for the same real close; the
        distinct metric name is deliberate so a reader can tell them
        apart rather than mistaking two real, independent observations
        for a duplicate. See 04-implement-test.md for why this wasn't
        deduplicated further.
        """
        if not symbol:
            return False
        try:
            resp = await self._http.get(
                f"{self._config.research_api_url}/research/hypotheses",
                params={"symbol": symbol},
            )
            if resp.status_code != 200:
                return False
            hypotheses = resp.json().get("hypotheses", [])
        except Exception as e:
            LOG.warning("Failed to look up hypotheses for %s: %s", symbol, e)
            return False

        active_ids = [
            h["hypothesis_id"] for h in hypotheses
            if h.get("status") in ("testing", "exploring", "monitoring") and h.get("hypothesis_id")
        ]
        if not active_ids:
            return False

        conclusion = "supports" if realized_return_pct >= 0 else "contradicts"
        reasoning = (
            f"Position closed for {symbol}"
            f"{f' (artifact {artifact_id})' if artifact_id else ''}: "
            f"realized return {realized_return_pct:.4%}."
        )

        wrote_any = False
        for hypothesis_id in active_ids:
            try:
                resp = await self._http.post(
                    f"{self._config.research_api_url}/research/hypotheses/{hypothesis_id}/evidence",
                    json={
                        "metric": "realized_return_pct",
                        "value": realized_return_pct,
                        "conclusion": conclusion,
                        "reasoning": reasoning,
                    },
                )
                wrote_any = wrote_any or resp.status_code == 200
            except Exception as e:
                LOG.warning("Failed to write evidence for hypothesis %s: %s", hypothesis_id, e)
        return wrote_any

    async def _write_ticker_ledger_closeout(
        self, symbol: str, artifact_id: str, realized_return_pct: float,
    ) -> bool:
        """The second write feedback_loop.py never made before Phase 5 --
        via vinu-agent's cross-container TickerLedger endpoint (Phase 0
        built the store, this is the first vinu-live writer to use it)."""
        if not symbol:
            return False
        try:
            resp = await self._http.post(
                f"{self._config.agent_api_url}/agent/ticker-ledger/event",
                json={
                    "ticker": symbol,
                    "stage": "monitor",
                    "event_type": "position_closed",
                    "text": f"Position closed, realized return {realized_return_pct:.4%}.",
                    "ref_id": artifact_id,
                    "source": "watchlist",
                },
            )
            return resp.status_code == 200
        except Exception as e:
            LOG.warning("Failed to write TickerLedger close-out row for %s: %s", symbol, e)
            return False

    async def _refresh_personality_stats(self, symbol: str) -> bool:
        """Targeted re-run of just Phase 2's shock angles for this symbol -- not the full
        21-angle suite, and not a no-op: a fresh `to_ts` on every call dodges the runner's
        dedup-skip (`has_existing_run` treats any prior completed run as "existing" once
        `from_ts`/`to_ts` are both None).
        """
        to_ts = int(datetime.now(timezone.utc).timestamp())
        try:
            resp = await self._http.post(
                f"{self._config.initial_analysis_api_url}/analysis/run/{symbol}",
                params={"angle_names": _PERSONALITY_ANGLES, "to_ts": to_ts},
            )
            return resp.status_code == 200
        except Exception as e:
            LOG.warning("Failed to refresh personality stats for %s: %s", symbol, e)
            return False
