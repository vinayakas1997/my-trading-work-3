from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from vinu_research.server.app import create_app
from vinu_research.service import ResearchService


@pytest.fixture
def service(storage, strategy_store):
    from vinu_research.config import ResearchConfig
    cfg = ResearchConfig()
    return ResearchService(config=cfg, storage=storage, strategy_store=strategy_store)


@pytest.fixture
def app(service):
    return create_app(service)


@pytest.fixture
def client(app):
    return TestClient(app)


class TestGetPaperReturn:
    """Regression for the dead ShadowEvaluator promotion gate: this route
    is the read-side (from vinu-live's perspective) producer of a BENCHING
    artifact's most recent paper-trading day -- nothing computed this at
    all before, so PaperPerformanceStore could never be fed (see
    high-expectations gate-conflict audit)."""

    def test_404_for_missing_artifact(self, client) -> None:
        resp = client.get("/research/artifacts/does-not-exist/paper-return")
        assert resp.status_code == 404

    def test_no_strategy_code_returns_no_data_status(self, client, strategy_store) -> None:
        from vinu_research.models import Artifact
        a = Artifact.create("strategy", "NoCode", universe=["AAPL"])
        a.strategy_code = ""
        strategy_store.upsert_artifact(a)

        resp = client.get(f"/research/artifacts/{a.artifact_id}/paper-return")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "no_strategy_code_or_universe"
        assert body["daily_return"] is None

    def test_no_universe_returns_no_data_status(self, client, strategy_store) -> None:
        from vinu_research.models import Artifact
        a = Artifact.create("strategy", "NoUniverse", universe=[])
        a.strategy_code = "class UserStrategy: pass"
        strategy_store.upsert_artifact(a)

        resp = client.get(f"/research/artifacts/{a.artifact_id}/paper-return")
        assert resp.status_code == 200
        assert resp.json()["status"] == "no_strategy_code_or_universe"

    def test_returns_last_daily_return_from_backtest(self, client, strategy_store, monkeypatch) -> None:
        from vinu_research.models import Artifact, BacktestMetrics, BacktestResult

        a = Artifact.create("strategy", "Real", universe=["AAPL"])
        a.strategy_code = "class UserStrategy: pass"
        strategy_store.upsert_artifact(a)

        async def _fake_run_backtest(self, **kw):
            return BacktestResult(
                run_id="r1", strategy_name="CustomStrategy", metrics=BacktestMetrics(),
                benchmark_metrics={}, trade_count=3, equity_points=6,
                raw={"daily_returns": [0.01, -0.005, 0.012]},
            )
        monkeypatch.setattr("vinu_research.tools.ResearchTools.run_backtest", _fake_run_backtest)

        resp = client.get(f"/research/artifacts/{a.artifact_id}/paper-return")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "ok"
        assert body["daily_return"] == 0.012
        assert body["symbol"] == "AAPL"

    def test_no_daily_returns_in_backtest_is_no_returns_status(self, client, strategy_store, monkeypatch) -> None:
        from vinu_research.models import Artifact, BacktestMetrics, BacktestResult

        a = Artifact.create("strategy", "Empty", universe=["AAPL"])
        a.strategy_code = "class UserStrategy: pass"
        strategy_store.upsert_artifact(a)

        async def _fake_run_backtest(self, **kw):
            return BacktestResult(
                run_id="r1", strategy_name="CustomStrategy", metrics=BacktestMetrics(),
                benchmark_metrics={}, trade_count=0, equity_points=0, raw={"daily_returns": []},
            )
        monkeypatch.setattr("vinu_research.tools.ResearchTools.run_backtest", _fake_run_backtest)

        resp = client.get(f"/research/artifacts/{a.artifact_id}/paper-return")
        assert resp.json()["status"] == "no_returns"

    def test_backtest_exception_does_not_500(self, client, strategy_store, monkeypatch) -> None:
        from vinu_research.models import Artifact

        a = Artifact.create("strategy", "Boom", universe=["AAPL"])
        a.strategy_code = "class UserStrategy: pass"
        strategy_store.upsert_artifact(a)

        async def _fake_run_backtest(self, **kw):
            raise RuntimeError("simulator unreachable")
        monkeypatch.setattr("vinu_research.tools.ResearchTools.run_backtest", _fake_run_backtest)

        resp = client.get(f"/research/artifacts/{a.artifact_id}/paper-return")
        assert resp.status_code == 200
        assert resp.json()["status"].startswith("backtest_failed")
