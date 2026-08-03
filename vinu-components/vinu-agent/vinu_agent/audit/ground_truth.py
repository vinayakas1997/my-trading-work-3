from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timezone
from typing import Any

from ..agent.tools import ToolRegistry

logger = logging.getLogger(__name__)

_GROUND_TRUTH_SENTINEL = "<ground-truth"


def _build_broker(as_of: str | None, session_id: str) -> Any:
    from ..broker.alpaca import AlpacaBroker
    from ..broker.historical_broker import HistoricalFillBroker

    if as_of:
        root = os.environ.get("VINU_AGENT_DATA_ROOT", "/data")
        state_path = os.path.join(root, "replay_state", f"{session_id}.json")
        return HistoricalFillBroker(as_of=as_of, state_path=state_path)
    return AlpacaBroker()


def _get_held_symbols(as_of: str | None, session_id: str) -> list[str]:
    try:
        broker = _build_broker(as_of, session_id)
        if not broker.is_configured():
            return []

        positions = broker.get_positions()
        return [p.symbol for p in positions if float(getattr(p, "qty", 0)) > 0]
    except Exception:
        return []


def _extract_latest_close(raw_json: str) -> float | None:
    try:
        data = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(data, dict):
        return None
    bars = data.get("data")
    if not isinstance(bars, list) or not bars:
        return None
    last = bars[-1]
    if not isinstance(last, dict):
        return None
    for key in ("close", "adj_close"):
        val = last.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


class GroundTruthInjector:
    """Force-fetches fresh prices for held positions before each turn so the
    agent cannot skip reality checks. Mirrors Vibe-Trading's grounding.py
    pattern — inject data before reasoning starts, don't try to detect
    skipped tool calls after the fact."""

    def __init__(
        self,
        registry: ToolRegistry,
        as_of: str | None = None,
        services_config: dict | None = None,
    ) -> None:
        self._registry = registry
        self._as_of = as_of
        self._services_config = services_config or {}

    def build_block(
        self, held_symbols: list[str], *, session_id: str = ""
    ) -> tuple[str | None, dict | None]:
        """Force-fetch latest close prices for *held_symbols* and return a
        (ground_truth_text, ground_truth_system_msg) pair, or (None, None) if
        there are no symbols or every fetch failed.

        The system message carries the ``<ground-truth`` sentinel so
        AgentLoop's compaction logic knows to preserve it across summarisation
        passes.
        """
        symbols = sorted(set(s for s in held_symbols if s))
        if not symbols:
            return None, None

        prices: dict[str, float] = {}
        fetch_ts = datetime.now(timezone.utc).isoformat()

        for sym in symbols:
            try:
                raw = self._registry.execute("get_stock_price", {"symbol": sym})
                price = _extract_latest_close(raw)
                if price is not None:
                    prices[sym] = price
            except Exception:
                logger.debug("Ground-truth fetch failed for %s", sym, exc_info=True)

        theses: dict[str, list[dict]] = self._fetch_open_theses(symbols)

        if not prices and not theses:
            return None, None

        lines = [
            f'{_GROUND_TRUTH_SENTINEL} as_of="{fetch_ts}">',
            "The following data was freshly fetched at session start. "
            "Do NOT state values for these symbols from memory or "
            "training data — only cite values that appear in this block or "
            "that come from a fresh tool call during this turn.",
            "",
        ]
        if prices:
            lines.append("## Fresh Prices")
            lines.append("")
            for sym in sorted(prices):
                lines.append(f"- {sym}: ${prices[sym]:.2f}  (fetched {fetch_ts})")
            lines.append("")
        if theses:
            lines.append("## Active Trade Theses (from Decision Journal)")
            lines.append("")
            for sym in sorted(theses):
                for th in theses[sym]:
                    status = th.get("status", "unknown")
                    thesis_text = th.get("thesis", "")[:300]
                    lines.append(f"- **{sym}** [{status}]: {thesis_text}")
            lines.append("")
        lines.append("</ground-truth>")

        block_text = "\n".join(lines)
        system_msg = {"role": "system", "content": block_text}

        try:
            from ..broker.kill_switch import AuditLogger
            AuditLogger.log(
                AuditLogger.GROUND_TRUTH_INJECTED,
                details={"prices": prices, "thesis_count": sum(len(v) for v in theses.values()), "as_of": self._as_of},
                session_id=session_id,
                symbol=",".join(sorted(set(list(prices) + list(theses)))),
            )
        except Exception:
            pass

        return block_text, system_msg

    @staticmethod
    def is_ground_truth_msg(msg: dict) -> bool:
        content = msg.get("content", "")
        if isinstance(content, str) and content.startswith(_GROUND_TRUTH_SENTINEL):
            return True
        return False

    def _fetch_open_theses(self, symbols: list[str]) -> dict[str, list[dict]]:
        """Query vinu-research's hypothesis registry for open (testing/exploring/
        monitoring) theses matching *symbols*. Returns {symbol: [thesis_dict, ...]}.
        Best-effort — API failure returns empty dict."""
        research_url = self._services_config.get("vinu_research")
        if not research_url:
            return {}

        import httpx

        result: dict[str, list[dict]] = {}
        try:
            resp = httpx.get(
                f"{research_url}/research/hypotheses",
                params={},
                timeout=5.0,
            )
            if resp.status_code != 200:
                return {}
            payload = resp.json()
        except Exception:
            return {}

        # GET /hypotheses returns {"count": N, "hypotheses": [...]}, not a
        # bare list (routes_introspect.py:list_hypotheses) — this previously
        # always fell through to {} below, silently disabling the "Active
        # Trade Theses" block.
        all_hypotheses = payload.get("hypotheses") if isinstance(payload, dict) else payload
        if not isinstance(all_hypotheses, list):
            return {}

        active_statuses = {"testing", "exploring", "monitoring"}

        for h in all_hypotheses:
            if not isinstance(h, dict):
                continue
            if h.get("status") not in active_statuses:
                continue
            universe = h.get("universe") or []
            for sym in symbols:
                if sym.upper() in [s.upper() for s in universe]:
                    result.setdefault(sym, []).append(h)
                    break

        return result
