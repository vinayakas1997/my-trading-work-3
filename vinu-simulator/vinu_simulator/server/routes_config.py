from __future__ import annotations

from fastapi import APIRouter

from vinu_simulator.server.schemas import SettingsResponse

router = APIRouter()
_get_settings = lambda: None


@router.get("/settings", response_model=SettingsResponse)
async def get_settings() -> SettingsResponse:
    s = _get_settings()
    if s is None:
        s = {}
    return SettingsResponse(
        initial_capital=s.get("initial_capital", 1_000_000.0),
        transaction_cost_pct=s.get("transaction_cost_pct", 0.001),
        slippage_pct=s.get("slippage_pct", 0.0005),
        benchmark_tickers=s.get("benchmark_tickers", ["SPY", "QQQ"]),
        allow_short=s.get("allow_short", True),
        strategy_api_url=s.get("strategy_api_url", ""),
        stock_api_url=s.get("stock_api_url", ""),
        deviation_threshold=s.get("deviation_threshold", 0.05),
    )
