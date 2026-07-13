from __future__ import annotations

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from vinu_simulator.server.routes_read import router as read_router
from vinu_simulator.server.routes_config import router as config_router
from vinu_simulator.service import SimulatorService


def create_app(service: SimulatorService | None = None) -> FastAPI:
    app_service = service or SimulatorService()
    owns_service = service is None

    import vinu_simulator.server.routes_read as rr
    rr._get_service = lambda: app_service

    import vinu_simulator.server.routes_config as rc
    rc._get_settings = lambda: _settings_from_config()

    app = FastAPI(
        title="vinu-simulator",
        description="Backtesting engine — realistic simulation with slippage, commission, position accounting",
        version="0.1.0",
    )

    app.include_router(read_router, prefix="", tags=["read"])
    app.include_router(config_router, prefix="", tags=["config"])

    static_dir = Path(__file__).resolve().parent / "static"
    if static_dir.exists():
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")

    return app


def _settings_from_config() -> dict:
    from vinu_simulator.config import load_config
    cfg = load_config()
    return {
        "initial_capital": cfg.initial_capital,
        "transaction_cost_pct": cfg.transaction_cost_pct,
        "slippage_pct": cfg.slippage_pct,
        "benchmark_tickers": list(cfg.benchmark_tickers),
        "allow_short": cfg.allow_short,
        "strategy_api_url": cfg.strategy_api_url,
        "stock_api_url": cfg.stock_api_url,
        "features_api_url": cfg.features_api_url,
        "deviation_threshold": cfg.deviation_threshold,
    }
