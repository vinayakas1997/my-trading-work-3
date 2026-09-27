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
def client(storage, tmp_path):
    from vinu_research.config import ResearchConfig

    # data_root=tmp_path: create_app() now also wires a real SweepGridStore
    # (item #3) at config.data_root / "sweep_grid.db" -- without this, a
    # bare ResearchConfig() would write a real file under the repo's cwd
    # every time this fixture runs.
    service = ResearchService(config=ResearchConfig(data_root=tmp_path), storage=storage)
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


class TestSweepPersistenceWiring:
    """item #3: POST /sweep/grid now persists the comparison for real
    (create_app() wires a real SweepGridStore, not just run_sweep_grid's
    own lazy default) -- these confirm the round-trip through the actual
    HTTP layer, not just the pure function tested in test_sweep_grid.py."""

    def test_response_includes_a_real_sweep_id(self, client) -> None:
        test_client, mock_tools = client
        mock_tools.run_backtest.side_effect = [_bt_result("r1", 1.0), _bt_result("r2", 2.0)]

        resp = test_client.post(
            "/research/sweep/grid",
            json={
                "symbol": "AAPL", "from_date": "2023-01-01", "to_date": "2023-12-31",
                "recipe": "crossover",
                "param_grid": [{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}],
            },
        )
        assert resp.json()["sweep_id"]

    def test_get_sweep_by_id_returns_the_full_comparison(self, client) -> None:
        test_client, mock_tools = client
        mock_tools.run_backtest.side_effect = [_bt_result("r1", 1.0), _bt_result("r2", 2.0)]

        post_resp = test_client.post(
            "/research/sweep/grid",
            json={
                "symbol": "AAPL", "from_date": "2023-01-01", "to_date": "2023-12-31",
                "recipe": "crossover",
                "param_grid": [{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}],
            },
        )
        sweep_id = post_resp.json()["sweep_id"]

        get_resp = test_client.get(f"/research/sweep/grid/{sweep_id}")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["symbol"] == "AAPL"
        assert len(body["points"]) == 2

    def test_get_unknown_sweep_id_is_404(self, client) -> None:
        test_client, _ = client
        assert test_client.get("/research/sweep/grid/ghost-id").status_code == 404

    def test_list_sweeps_filters_by_symbol(self, client) -> None:
        test_client, mock_tools = client
        mock_tools.run_backtest.side_effect = [
            _bt_result("r1", 1.0), _bt_result("r2", 1.0), _bt_result("r3", 1.0),
        ]
        test_client.post(
            "/research/sweep/grid",
            json={
                "symbol": "AAPL", "from_date": "2023-01-01", "to_date": "2023-12-31",
                "recipe": "crossover", "param_grid": [{"fast_period": 5, "slow_period": 40}],
            },
        )
        test_client.post(
            "/research/sweep/grid",
            json={
                "symbol": "AAPL", "from_date": "2023-01-01", "to_date": "2023-12-31",
                "recipe": "crossover", "param_grid": [{"fast_period": 6, "slow_period": 40}],
            },
        )
        test_client.post(
            "/research/sweep/grid",
            json={
                "symbol": "MSFT", "from_date": "2023-01-01", "to_date": "2023-12-31",
                "recipe": "crossover", "param_grid": [{"fast_period": 5, "slow_period": 40}],
            },
        )

        resp = test_client.get("/research/sweep/grid", params={"symbol": "AAPL"})
        assert resp.status_code == 200
        sweeps = resp.json()["sweeps"]
        assert len(sweeps) == 2
        assert all(s["symbol"] == "AAPL" for s in sweeps)
