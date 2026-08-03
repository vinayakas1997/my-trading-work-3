"""Debrief-on-close — the missing read-back half of item 3's decision
journal. `trade_plan_tool.py`'s `_schedule_journal_write` records a thesis
into vinu-research's HypothesisRegistry when a plan is generated, but
nothing wrote the outcome back when the position actually closed, so a
thesis just sat unresolved forever. See
`04-agentic-still-refinement/implementation-plan-from-04/vinu-agent/plan.md`
Piece 2 for why this matters.

Detection is a before/after diff of held positions (there is no fill-event
webhook in this codebase — `AlpacaBroker`/`HistoricalFillBroker` are both
polled on demand) rather than a new polling process: whichever caller
already calls `broker.get_positions()` once per turn (mirroring
`GroundTruthInjector`) also calls `check_and_debrief()`, which persists the
previously-seen position snapshot and reports any symbol that dropped out.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

_ACTIVE_THESIS_STATUSES = {"testing", "exploring", "monitoring"}


def _load_state(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(path: Path, state: dict[str, dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


class PositionCloseDetector:
    """Best-effort: any failure here is logged and swallowed, never raised —
    this is an audit/learning aid, not part of the trade path."""

    def __init__(
        self,
        registry: Any,
        state_path: str | Path,
        services_config: dict | None = None,
    ) -> None:
        self._registry = registry
        self._state_path = Path(state_path)
        self._services_config = services_config or {}

    def check_and_debrief(self, broker: Any, session_id: str = "") -> list[dict]:
        try:
            current = {
                p.symbol: {"qty": float(p.qty), "avg_entry_price": float(p.avg_entry_price)}
                for p in broker.get_positions()
                if float(p.qty) > 0
            }
        except Exception:
            logger.debug("PositionCloseDetector: get_positions failed", exc_info=True)
            return []

        previous = _load_state(self._state_path)
        closed_symbols = [s for s in previous if s not in current]

        results: list[dict] = []
        for sym in closed_symbols:
            outcome = self._debrief_one(sym, previous[sym], session_id)
            if outcome is not None:
                results.append(outcome)

        _save_state(self._state_path, current)
        return results

    def _debrief_one(self, symbol: str, entry: dict, session_id: str) -> dict | None:
        exit_price = self._fetch_exit_price(symbol)
        if exit_price is None:
            return None

        qty = entry.get("qty", 0.0)
        avg_entry_price = entry.get("avg_entry_price", 0.0)
        realized_pnl = (exit_price - avg_entry_price) * qty

        thesis_ids = self._fetch_open_thesis_ids(symbol)
        conclusion = "supports" if realized_pnl >= 0 else "contradicts"
        reasoning = (
            f"Position closed. Entry ~${avg_entry_price:.2f}, exit ~${exit_price:.2f}, "
            f"qty {qty:g} -> realized P&L ${realized_pnl:.2f}."
        )

        updated = 0
        for hypothesis_id in thesis_ids:
            if self._write_evidence(hypothesis_id, realized_pnl, conclusion, reasoning):
                updated += 1

        try:
            from .kill_switch import AuditLogger

            AuditLogger.log(
                AuditLogger.JOURNAL_STATUS_CHANGED,
                details={"symbol": symbol, "realized_pnl": realized_pnl, "theses_updated": updated},
                session_id=session_id,
                symbol=symbol,
            )
        except Exception:
            pass

        return {"symbol": symbol, "realized_pnl": realized_pnl, "theses_updated": updated}

    def _fetch_exit_price(self, symbol: str) -> float | None:
        try:
            raw = self._registry.execute("get_stock_price", {"symbol": symbol})
        except Exception:
            return None
        from ..audit.ground_truth import _extract_latest_close

        return _extract_latest_close(raw)

    def _fetch_open_thesis_ids(self, symbol: str) -> list[str]:
        research_url = self._services_config.get("vinu_research")
        if not research_url:
            return []

        import httpx

        try:
            resp = httpx.get(f"{research_url}/research/hypotheses", params={}, timeout=5.0)
            if resp.status_code != 200:
                return []
            payload = resp.json()
        except Exception:
            return []

        all_hypotheses = payload.get("hypotheses") if isinstance(payload, dict) else payload
        if not isinstance(all_hypotheses, list):
            return []

        result: list[str] = []
        for h in all_hypotheses:
            if not isinstance(h, dict) or h.get("status") not in _ACTIVE_THESIS_STATUSES:
                continue
            universe = h.get("universe") or []
            if symbol.upper() in [s.upper() for s in universe]:
                result.append(h.get("hypothesis_id"))
        return result

    def _write_evidence(
        self, hypothesis_id: str | None, realized_pnl: float, conclusion: str, reasoning: str
    ) -> bool:
        research_url = self._services_config.get("vinu_research")
        if not research_url or not hypothesis_id:
            return False

        import httpx

        try:
            resp = httpx.post(
                f"{research_url}/research/hypotheses/{hypothesis_id}/evidence",
                json={
                    "metric": "realized_pnl",
                    "value": realized_pnl,
                    "conclusion": conclusion,
                    "reasoning": reasoning,
                },
                timeout=10.0,
            )
            return resp.status_code == 200
        except Exception:
            return False
