"""Point 5's trigger route (reverse-engineering/
06-execution-handoff-and-architecture.md's point 5/8, "not decided"
until now): vinu-live's candle-close poller calls this the instant a
(ticker, strategy) pair reaches `ready_to_execute`, so the
`live_decision` team actually gets run -- closes the last gap in the
live decision loop (points 2-4 were already wired to nothing consuming
`ready_to_execute`).

Reuses the already-running AgentService's own SessionService
(`run_team_once`, session/service.py) rather than standing up a second
LLM client/store set -- same `_get_service` module-level wiring pattern
every other route file in this directory already uses.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()
LOG = logging.getLogger(__name__)

_get_service: Any = lambda: None

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(content: str) -> dict | None:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


class LiveDecisionRequest(BaseModel):
    ticker: str
    strategy_id: str
    trigger_id: str | None = None
    # Exit-mechanism fix (missing-pieces-of-system/new-theory-of-trading/
    # system-wide-audit-and-design/04-synthesis-built-vs-missing-2026-09-28.md):
    # "entry" is the original ready_to_execute call (EXECUTE/SKIP/
    # EXTEND_GRACE_WINDOW); "review" is vinu-live's periodic check on an
    # already-open live_decision position (HOLD/EXIT). Same team/agent,
    # same route -- the mode only changes which section of the agent's
    # own prompt.md applies and what task context is given.
    mode: str = "entry"
    position_context: dict[str, Any] | None = None
    # v2 B1: set by vinu-live only when its input-novelty check says the live features are unlike recent history.
    novelty: dict[str, Any] | None = None


@router.post("/live-decision/run")
async def run_live_decision(body: LiveDecisionRequest) -> dict[str, Any]:
    svc = _get_service()
    if svc is None:
        raise HTTPException(status_code=503, detail="agent service not available")

    ticker = body.ticker.upper()
    task = f"Ticker: {ticker}\nStrategy: {body.strategy_id}"
    if body.trigger_id:
        task += f"\nTrigger id: {body.trigger_id}"

    if body.novelty and body.novelty.get("novelty_high"):
        task += (
            f"\nInput novelty: HIGH (dissimilarity ratio {body.novelty.get('ratio')}; this ticker's current features are "
            "unlike its recent recorded history). Treat the historical evidence as weaker than usual and prefer SKIP "
            "unless the case is clearly strong."
        )

    if body.mode == "review":
        task += "\nMode: POSITION_REVIEW"
        ctx = body.position_context or {}
        task += (
            f"\nOpen position: opened_at={ctx.get('opened_at', 'unknown')}, "
            f"opened_bar_ts={ctx.get('opened_bar_ts', 'unknown')}, "
            f"position_size={ctx.get('position_size', 'unknown')}"
        )
        # Real facts only (features-logic-checking D6); a missing field is unknown, never zero.
        facts = [f"{k}={ctx[k]}" for k in ("entry_price", "last_close", "return_since_entry", "bars_held")
                 if ctx.get(k) is not None]
        if facts:
            task += "\nPosition so far (plain numbers, before costs): " + ", ".join(facts)

    result = svc.session_service.run_team_once(
        "live_decision", task, tag=f"{ticker}-{body.strategy_id}",
    )
    if result.get("status") != "completed":
        return {
            "status": "error", "ticker": ticker, "strategy_id": body.strategy_id,
            "error": "live_decision team did not complete", "detail": result,
        }

    decision_data = _extract_json_block(result.get("content", "")) or {}
    return {
        "status": "ok",
        "ticker": ticker,
        "strategy_id": body.strategy_id,
        "decision": decision_data.get("decision", ""),
        "precondition_held": decision_data.get("precondition_held"),
        "reasoning": decision_data.get("reasoning", ""),
        "content": result.get("content", ""),
    }
