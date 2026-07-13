from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from vinu_strategy.api import StrategyAPI

router = APIRouter()
_api: StrategyAPI | None = None


def _get_api() -> StrategyAPI:
    global _api
    if _api is None:
        _api = StrategyAPI()
    return _api


@router.get("/strategies")
async def list_strategies() -> list[dict[str, Any]]:
    return _get_api().list_strategies()


@router.get("/strategies/{name}")
async def get_strategy(name: str) -> dict[str, Any]:
    result = _get_api().get_strategy(name)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Strategy '{name}' not found")
    return result


@router.post("/strategies/{name}/evaluate")
async def evaluate_strategy(
    name: str,
    symbols: list[str] | None = Query(default=None),
) -> dict[str, Any]:
    return _get_api().evaluate(name, symbols)


@router.get("/weights")
async def get_weights(
    strategy: str = Query(default="ma_crossover"),
    symbol: str | None = Query(default=None),
    from_ts: int | None = Query(default=None),
    to_ts: int | None = Query(default=None),
) -> list[dict[str, Any]]:
    return _get_api().get_weights(strategy, symbol, from_ts, to_ts)


@router.get("/runs")
async def get_runs(
    strategy: str | None = Query(default=None),
) -> list[dict[str, Any]]:
    return _get_api().get_runs(strategy)


@router.delete("/weights/{strategy}")
async def delete_weights(
    strategy: str,
    symbol: str | None = Query(default=None),
) -> dict[str, Any]:
    return _get_api().delete_weights(strategy, symbol)


@router.delete("/runs")
async def delete_runs(
    strategy: str | None = Query(default=None),
) -> dict[str, Any]:
    return _get_api().delete_runs(strategy)


@router.delete("/runs/{run_id}")
async def delete_run_by_id(run_id: str) -> dict[str, Any]:
    return _get_api().delete_run_by_id(run_id)


@router.get("/docs/yaml-reference")
async def yaml_reference() -> PlainTextResponse:
    guide_path = Path(__file__).resolve().parent.parent.parent / "YAML-REFERENCE.md"
    if not guide_path.exists():
        raise HTTPException(status_code=404, detail="YAML reference not found")
    return PlainTextResponse(guide_path.read_text())
