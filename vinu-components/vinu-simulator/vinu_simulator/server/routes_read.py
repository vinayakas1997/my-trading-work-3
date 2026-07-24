from __future__ import annotations

import asyncio
from functools import partial
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Query

from vinu_simulator.server.schemas import (
    CustomSimulateRequest,
    CustomSimulateResponse,
    HealthResponse,
    RunSummary,
    SimulateRequest,
    SimulateResponse,
)
from vinu_simulator.service import SimulatorService

router = APIRouter()
_get_service: Any = lambda: None


async def _run_sync(callable: Any, *args: Any, **kwargs: Any) -> Any:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, partial(callable, *args, **kwargs))


async def _check_service(base_url: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{base_url}/health")
            return resp.status_code == 200
    except Exception:
        return False


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    svc: SimulatorService = _get_service()
    strategy_ok = await _check_service(svc._strategy_client._base_url)
    stock_ok = await _check_service(svc._price_client._base_url)
    features_ok = await _check_service(svc._features_client._base_url)
    return HealthResponse(
        strategy_api_healthy=strategy_ok,
        stock_api_healthy=stock_ok,
        features_api_healthy=features_ok,
    )


@router.post("/simulate", response_model=SimulateResponse)
async def simulate(req: SimulateRequest) -> SimulateResponse:
    svc: SimulatorService = _get_service()
    result = await _run_sync(svc.simulate, req)
    return SimulateResponse(
        run_id=result.run_id,
        strategy_name=result.strategy_name,
        timestamp=result.timestamp,
        metrics=result.metrics,
        benchmark_metrics=result.benchmark_metrics,
        trade_count=len(result.trades),
        equity_points=len(result.portfolio_values),
        validation=result.validation,
    )


@router.post("/simulate/custom", response_model=CustomSimulateResponse)
async def simulate_custom(req: CustomSimulateRequest) -> CustomSimulateResponse:
    svc: SimulatorService = _get_service()
    result = await _run_sync(svc.simulate_custom, req)
    return CustomSimulateResponse(
        run_id=result.run_id,
        strategy_name=result.strategy_name,
        timestamp=result.timestamp,
        metrics=result.metrics,
        benchmark_metrics=result.benchmark_metrics,
        trade_count=len(result.trades),
        equity_points=len(result.portfolio_values),
        validation=result.validation,
    )


@router.get("/results/{run_id}")
async def get_run_result(run_id: str) -> dict[str, Any]:
    svc = _get_service()
    result = await _run_sync(svc.get_result, run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return result


@router.get("/results/{run_id}/metrics")
async def get_run_metrics(run_id: str) -> dict[str, Any]:
    svc = _get_service()
    result = await _run_sync(svc.get_result, run_id, load_data=False)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return {
        "run_id": run_id,
        "metrics": result["metrics"],
        "benchmark_metrics": result.get("benchmark_metrics", {}),
    }


@router.get("/results/{run_id}/equity")
async def get_run_equity(run_id: str) -> list[dict[str, Any]]:
    svc = _get_service()
    equity = await _run_sync(svc.get_equity, run_id)
    if equity is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return equity


@router.get("/results/{run_id}/weights")
async def get_run_weights(run_id: str) -> list[dict[str, Any]]:
    svc = _get_service()
    weights = await _run_sync(svc.get_weights, run_id)
    if weights is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return weights


@router.get("/results/{run_id}/trades")
async def get_run_trades(run_id: str) -> list[dict[str, Any]]:
    svc = _get_service()
    trades = await _run_sync(svc.get_trades, run_id)
    if trades is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return trades


@router.get("/runs")
async def list_runs(
    strategy: str | None = Query(default=None),
    symbol: str | None = Query(default=None),
) -> list[RunSummary]:
    svc = _get_service()
    return await _run_sync(svc.list_runs, strategy, symbol)


@router.delete("/runs/{run_id}")
async def delete_run(run_id: str) -> dict[str, Any]:
    svc = _get_service()
    deleted = await _run_sync(svc.delete_run, run_id)
    return {"deleted": deleted}


@router.delete("/runs")
async def delete_runs(
    strategy: str | None = Query(default=None),
) -> dict[str, Any]:
    svc = _get_service()
    count = await _run_sync(svc.delete_runs, strategy)
    return {"deleted": count}
