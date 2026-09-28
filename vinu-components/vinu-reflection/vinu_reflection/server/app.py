from __future__ import annotations

from fastapi import APIRouter

from vinu_infra.reflection import ReflectionStore
from vinu_infra.server import create_app as _create_app
from vinu_reflection.config import ReflectionConfig
from vinu_reflection.server import routes_synthesis


def create_app(config: ReflectionConfig | None = None, store: ReflectionStore | None = None):
    from vinu_reflection.config import load_config

    cfg = config or load_config()
    reflection_store = store or ReflectionStore(cfg.data_root / "reflection.db")
    routes_synthesis.set_store(reflection_store)

    merged = APIRouter()
    merged.include_router(routes_synthesis.router, tags=["synthesis"])

    return _create_app(
        service_name="vinu-reflection",
        version="0.1.0",
        description="Reflection layer — 24 analysts plus the maturity-synthesis brain (Step 8/9)",
        router=merged,
        static_dir=None,
        expose_health_on_root=False,
        route_prefix="reflection",
    )
