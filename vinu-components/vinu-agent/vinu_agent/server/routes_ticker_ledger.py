"""HTTP-exposed TickerLedger write -- the cross-container front door onto
storage/ticker_ledger.py's TickerLedgerStore (Phase 0). Every existing
TickerLedger writer so far (risk_gatekeeper_hook.py, capital_allocator_
hook.py) runs in-process inside vinu-agent itself; vinu-live runs in a
separate container with no filesystem access to vinu-agent's /data volume
and no in-process import boundary in the real deployment, so a
cross-service writer (Phase 5's feedback_loop.py close-out path) needs an
HTTP route, same reasoning as routes_broker.py's own module docstring for
why the Kill Switch is HTTP-fronted rather than file-based.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

router = APIRouter()


def _get_service() -> Any:
    raise RuntimeError("AgentService dependency not configured")


class TickerLedgerEventRequest(BaseModel):
    ticker: str = Field(..., min_length=1)
    stage: str = Field(..., min_length=1)
    event_type: str = Field(..., min_length=1)
    text: str = ""
    ref_id: str = ""
    source: str = "watchlist"


@router.post("/ticker-ledger/event")
async def add_ticker_ledger_event(body: TickerLedgerEventRequest) -> dict[str, Any]:
    service = _get_service()
    event = service.ticker_ledger.add_event(
        ticker=body.ticker, stage=body.stage, event_type=body.event_type,
        text=body.text, ref_id=body.ref_id, source=body.source,
    )
    return {
        "status": "ok",
        "ledger_id": event.ledger_id,
        "ticker": event.ticker,
        "stage": event.stage,
        "event_type": event.event_type,
    }
