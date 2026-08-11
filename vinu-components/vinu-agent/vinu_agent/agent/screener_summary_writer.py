"""Turns the screener team's final answer into durable per-ticker
summaries in TickerSummaryStore. Never an agent tool (pillar 8) -- called
from TeamManager.run() after the manager's final answer is parsed, same
shape as research_artifact_writer.py / risk_gatekeeper_hook.py.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

LOG = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(content: str) -> Optional[dict]:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def write_ticker_summaries(
    content: str, *, ticker_summary_store: Any, source_run_id: str = "",
) -> list[str]:
    """Best-effort: any failure here is logged and swallowed, never raised
    (same contract as broker/debrief.py). Returns the list of tickers
    actually written, so the caller can attach it to the run's result for
    traceability -- empty list means nothing was written (malformed block,
    empty ticker list, or a store failure), not necessarily an error.
    """
    try:
        data = _extract_json_block(content)
        if not data:
            return []
        tickers = data.get("tickers")
        if not isinstance(tickers, dict) or not tickers:
            return []
    except Exception:
        LOG.exception("failed to parse screener summary block, continuing without it")
        return []

    written: list[str] = []
    for ticker, info in tickers.items():
        try:
            if not isinstance(info, dict):
                continue
            summary = str(info.get("summary", "")).strip()
            if not ticker or not summary:
                continue
            ticker_summary_store.upsert_summary(
                str(ticker).strip().upper(),
                summary,
                angles_with_data=int(info.get("angles_with_data", 0) or 0),
                angle_count=int(info.get("angle_count", 0) or 0),
                source_run_id=source_run_id,
            )
            written.append(str(ticker).strip().upper())
        except Exception:
            LOG.exception("failed to write summary for ticker %r, continuing with the rest", ticker)
    return written
