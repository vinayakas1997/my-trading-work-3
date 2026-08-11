"""Route-level test for POST /sweep/grid -- confirms the Pydantic request
model, run_sweep_grid, and the JSON serialization actually agree with each
other end to end (a mocked ResearchTools is swapped in after create_app()
via the same set_tools() hook the app itself uses, no live simulator
needed)."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from vinu_research.models import BacktestMetrics, BacktestResult
from vinu_research.server import routes_sweep
from vinu_research.server.app import create_app
from vinu_research.service import ResearchService


def _bt_result(run_id: str, sharpe: float) -> BacktestResult:
    return BacktestResult(
        run_id=run_id,
        strategy_name="UserStrategy",
        metrics=BacktestMetrics(sharpe_ratio=sharpe, total_return=0.05, max_drawdown=-0.1, win_rate=0.55),
        benchmark_metrics={},
        trade_count=42,
        equity_points=100,
        raw={"equity_points": 100, "benchmark_metrics": {}},
    )


@pytest.fixture
def client(storage):
    from vinu_research.config import ResearchConfig

    service = ResearchService(config=ResearchConfig(), storage=storage)
    app = create_app(service)
    mock_tools = AsyncMock()
    routes_sweep.set_tools(mock_tools)
    with TestClient(app) as test_client:
        yield test_client, mock_tools


def test_sweep_grid_returns_ranked_table(client) -> None:
    test_client, mock_tools = client
    mock_tools.run_backtest.side_effect = [_bt_result("r1", 1.0), _bt_result("r2", 2.0)]

    resp = test_client.post(
        "/research/sweep/grid",
        json={
            "symbol": "AAPL",
            "from_date": "2023-01-01",
            "to_date": "2023-12-31",
            "recipe": "crossover",
            "param_grid": [{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["requested"] == 2
    assert body["succeeded"] == 2
    assert body["completeness"] == 1.0
    assert len(body["ranked"]) == 2


def test_sweep_grid_oversized_grid_is_422(client) -> None:
    test_client, mock_tools = client
    oversized = [{"fast_period": i, "slow_period": 40} for i in range(50)]

    resp = test_client.post(
        "/research/sweep/grid",
        json={
            "symbol": "AAPL", "from_date": "2023-01-01", "to_date": "2023-12-31",
            "recipe": "crossover", "param_grid": oversized,
        },
    )
    assert resp.status_code == 422
    mock_tools.run_backtest.assert_not_awaited()


def test_sweep_grid_both_modes_is_400(client) -> None:
    test_client, _ = client
    resp = test_client.post(
        "/research/sweep/grid",
        json={
            "symbol": "AAPL", "from_date": "2023-01-01", "to_date": "2023-12-31",
            "recipe": "crossover", "base_code": "class X: pass",
            "param_grid": [{"fast_period": 5}],
        },
    )
    assert resp.status_code == 422  # pydantic model_validator raises during request parsing
