"""Group 1 quant-core fold (component-consolidation-plan.md): serves
vinu-strategy's and vinu-simulator's real routes from one process, one
deploy artifact, instead of two separate containers -- the lowest-risk
fold in that plan (both are confirmed genuinely stateless: pure
request/response APIs, no background worker, unlike the other four Group
1 services).

Deliberately does NOT go through either side's own
`server/app.py::create_app()` (each of those already calls
`vinu_infra.server.create_app()`, producing a *complete* standalone
FastAPI app object) -- mounting one finished ASGI app inside another
would rely on Starlette propagating the parent's lifespan into mounted
sub-apps, a real, easy-to-get-wrong ASGI subtlety not worth risking here.
Instead this imports each side's routers and wiring hooks directly (both
already public, already the real thing each `create_app()` uses
internally) and calls `vinu_infra.server.create_app()` itself, exactly
once, the same shape every other service in this codebase already uses --
just combining two routers' worth of real code instead of one.

Path namespaces are unchanged: `/strategy/*` and `/simulator/*`, exactly
what each container serves today under its own `route_prefix`. Every
existing consumer's URL *path* is therefore identical after this fold --
only the *host:port* both now share changes (see
`component-consolidation-plan.md` and `.env`/`.env-example` for the
merged `VINU_STRATEGY_API_URL`/`VINU_SIMULATOR_API_URL` values).
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import APIRouter

from vinu_infra.server import create_app as _create_app
from vinu_strategy.server.routes_config import router as strategy_config_router
from vinu_strategy.server.routes_read import router as strategy_read_router


@asynccontextmanager
async def _lifespan(app):
    # Mirrors vinu_strategy/server/app.py's own lifespan, plus one real fix:
    # routes_config.set_service() was never called anywhere in the original
    # codebase either, so /strategy/health always fell into its "Service
    # not initialized" branch (a pre-existing bug, confirmed independent of
    # this merge -- same in app.py's own lifespan, just masked there by
    # route-registration order in some setups). Wired here since this is
    # the actually-deployed entrypoint.
    from vinu_strategy.server.routes_config import set_service
    from vinu_strategy.server.routes_read import _get_api

    api = await asyncio.to_thread(_get_api)
    set_service(api._service)
    yield


def _wire_simulator_routers() -> tuple[APIRouter, APIRouter]:
    """Mirrors vinu_simulator/server/app.py's own runtime-monkeypatch
    wiring exactly -- its routes read module-level `_get_service`/
    `_get_settings` hooks rather than taking them as constructor args, so
    this reproduces that same wiring here instead of going through its
    create_app() (see this module's own docstring for why)."""
    import vinu_simulator.server.routes_config as sim_routes_config
    import vinu_simulator.server.routes_read as sim_routes_read
    from vinu_simulator.service import SimulatorService

    service = SimulatorService()
    sim_routes_read._get_service = lambda: service

    def _settings() -> dict:
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

    sim_routes_config._get_settings = _settings
    return sim_routes_read.router, sim_routes_config.router


def create_merged_app():
    simulator_read_router, simulator_config_router = _wire_simulator_routers()

    merged = APIRouter()
    merged.include_router(strategy_read_router, prefix="/strategy", tags=["strategy-read"])
    merged.include_router(strategy_config_router, prefix="/strategy", tags=["strategy-config"])
    merged.include_router(simulator_read_router, prefix="/simulator", tags=["simulator-read"])
    merged.include_router(simulator_config_router, prefix="/simulator", tags=["simulator-config"])

    # expose_health_on_root=False: _create_app's own health route is a
    # single path tied to one route_prefix, and can't serve both
    # /strategy/health and /simulator/health -- moot anyway, since
    # routes_config.py on each side already defines its own real /health
    # handler, which lands at the right merged path once included above
    # (docker-compose's healthcheck targets keep working unchanged).
    return _create_app(
        service_name="vinu-quant-core",
        version="0.1.0",
        description=(
            "Merged vinu-strategy + vinu-simulator (Group 1 fold, "
            "component-consolidation-plan.md) -- decision fusion and "
            "backtesting, one deploy artifact instead of two."
        ),
        router=merged,
        lifespan=_lifespan,
        expose_health_on_root=False,
        route_prefix=None,
    )
