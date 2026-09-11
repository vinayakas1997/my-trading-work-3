from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from vinu_screener.audit.watch_history import WatchAuditStore
from vinu_screener.rankers.snapshot_store import RankedSnapshotStore
from vinu_screener.rankers.store import RankerStore
from vinu_screener.rules.store import RuleStore
from vinu_screener.server.app import create_app


def _ohlcv(close: list[float]) -> pd.DataFrame:
    c = np.array(close, dtype=float)
    return pd.DataFrame({"open": c, "high": c + 0.1, "low": c - 0.1, "close": c, "volume": np.full(len(c), 1000.0)})


class FakeDataSource:
    def __init__(self) -> None:
        self.frames: dict[str, pd.DataFrame] = {}

    def get_ohlcv(self, symbol: str):
        return self.frames.get(symbol)

    def get_snapshot(self, symbol: str):
        return None


@pytest.fixture
def data_source() -> FakeDataSource:
    ds = FakeDataSource()
    ds.frames["AAPL"] = _ohlcv([90, 95, 105])
    return ds


@pytest.fixture
def client(data_source: FakeDataSource, tmp_path: Path) -> TestClient:
    # Real files, not ":memory:" -- FastAPI dispatches sync routes onto a
    # threadpool, and SQLite's ":memory:" is per-*connection*, not shared
    # across a process the way a real file path is; a request handled on a
    # different worker thread than the one that created the rule would see
    # an empty database. A real file (even a throwaway tmp_path one) is
    # what production actually uses, so it's what the test should too.
    app = create_app(
        rule_store=RuleStore(tmp_path / "rules.db"),
        audit_store=WatchAuditStore(tmp_path / "audit.db"),
        data_source=data_source,
        ranker_store=RankerStore(tmp_path / "rankers.db"),
        ranker_snapshot_store=RankedSnapshotStore(tmp_path / "ranker_snapshots.db"),
    )
    return TestClient(app)


_RULE_BODY = {
    "condition": {"indicator": "close", "operator": ">", "value": 100.0},
    "universe": ["AAPL"],
}


class TestRuleCrud:
    def test_create_then_get(self, client: TestClient) -> None:
        put = client.put("/screener/rules/r1", json=_RULE_BODY)
        assert put.status_code == 200
        get = client.get("/screener/rules/r1")
        assert get.status_code == 200
        assert get.json()["rule_id"] == "r1"
        assert get.json()["universe"] == ["AAPL"]

    def test_get_unknown_rule_is_404(self, client: TestClient) -> None:
        assert client.get("/screener/rules/ghost").status_code == 404

    def test_list_includes_every_created_rule(self, client: TestClient) -> None:
        client.put("/screener/rules/r1", json=_RULE_BODY)
        client.put("/screener/rules/r2", json=_RULE_BODY)
        rules = client.get("/screener/rules").json()["rules"]
        assert {r["rule_id"] for r in rules} == {"r1", "r2"}

    def test_malformed_condition_is_422(self, client: TestClient) -> None:
        resp = client.put("/screener/rules/r1", json={"condition": {"bad": "shape"}, "universe": ["AAPL"]})
        assert resp.status_code == 422

    def test_delete_removes_the_rule(self, client: TestClient) -> None:
        client.put("/screener/rules/r1", json=_RULE_BODY)
        resp = client.delete("/screener/rules/r1")
        assert resp.json()["deleted"] is True
        assert client.get("/screener/rules/r1").status_code == 404

    def test_update_preserves_rule_id_and_replaces_body(self, client: TestClient) -> None:
        client.put("/screener/rules/r1", json=_RULE_BODY)
        client.put("/screener/rules/r1", json={**_RULE_BODY, "cooldown_min": 15.0})
        assert client.get("/screener/rules/r1").json()["cooldown_min"] == 15.0


class TestEnableDisable:
    def test_disable_then_enable_round_trips(self, client: TestClient) -> None:
        client.put("/screener/rules/r1", json=_RULE_BODY)
        d = client.post("/screener/rules/r1/disable")
        assert d.json()["active"] is False
        assert client.get("/screener/rules/r1").json()["active"] is False
        e = client.post("/screener/rules/r1/enable")
        assert e.json()["active"] is True

    def test_disable_unknown_rule_is_404(self, client: TestClient) -> None:
        assert client.post("/screener/rules/ghost/disable").status_code == 404


class TestDryRun:
    def test_dry_run_reports_triggered_symbol(self, client: TestClient) -> None:
        client.put("/screener/rules/r1", json=_RULE_BODY)
        resp = client.post("/screener/rules/r1/dry-run")
        assert resp.status_code == 200
        body = resp.json()
        assert body["triggered"] == ["AAPL"]
        assert body["counts"]["triggered"] == 1

    def test_dry_run_on_unknown_rule_is_404(self, client: TestClient) -> None:
        assert client.post("/screener/rules/ghost/dry-run").status_code == 404


class TestFiredHistory:
    def test_history_is_empty_before_any_fire_is_recorded(self, client: TestClient) -> None:
        client.put("/screener/rules/r1", json=_RULE_BODY)
        resp = client.get("/screener/rules/r1/history")
        assert resp.json()["history"] == []


class TestPairlistTokenDefaultsToTheSharedInternalKey:
    """The pairlist route is mounted inside the same app `create_app()`
    wraps in `Depends(require_auth)` (VINU_API_KEY) for the whole router --
    if the pairlist route's OWN bearer check used a different default
    token, the same Authorization header could never satisfy both checks
    at once, and every pairlist request would 401 whenever VINU_API_KEY is
    set. DEFAULT_PAIRLIST_TOKEN must fall back to VINU_API_KEY itself so
    the common single-shared-token deployment just works."""

    def test_falls_back_to_vinu_api_key_when_unset(self, monkeypatch) -> None:
        import importlib

        monkeypatch.delenv("VINU_SCREENER_PAIRLIST_TOKEN", raising=False)
        monkeypatch.setattr("vinu_infra.auth.VINU_API_KEY", "shared-secret")
        import vinu_screener.server.app as app_mod

        importlib.reload(app_mod)
        try:
            assert app_mod.DEFAULT_PAIRLIST_TOKEN == "shared-secret"
        finally:
            monkeypatch.setattr("vinu_infra.auth.VINU_API_KEY", "")
            importlib.reload(app_mod)

    def test_explicit_override_wins_over_vinu_api_key(self, monkeypatch) -> None:
        import importlib

        monkeypatch.setenv("VINU_SCREENER_PAIRLIST_TOKEN", "screener-only-token")
        monkeypatch.setattr("vinu_infra.auth.VINU_API_KEY", "shared-secret")
        import vinu_screener.server.app as app_mod

        importlib.reload(app_mod)
        try:
            assert app_mod.DEFAULT_PAIRLIST_TOKEN == "screener-only-token"
        finally:
            monkeypatch.delenv("VINU_SCREENER_PAIRLIST_TOKEN", raising=False)
            monkeypatch.setattr("vinu_infra.auth.VINU_API_KEY", "")
            importlib.reload(app_mod)


_RANKER_BODY = {
    "universe": ["AAPL"],
    "factors": [{"name": "momentum", "indicator": "close", "weight": 1.0}],
    "top_n": 10,
}


class TestRankerCrud:
    def test_create_then_get(self, client: TestClient) -> None:
        put = client.put("/screener/rankers/r1", json=_RANKER_BODY)
        assert put.status_code == 200
        get = client.get("/screener/rankers/r1")
        assert get.status_code == 200
        assert get.json()["ranker_id"] == "r1"
        assert get.json()["universe"] == ["AAPL"]

    def test_get_unknown_ranker_is_404(self, client: TestClient) -> None:
        assert client.get("/screener/rankers/ghost").status_code == 404

    def test_list_includes_every_created_ranker(self, client: TestClient) -> None:
        client.put("/screener/rankers/r1", json=_RANKER_BODY)
        client.put("/screener/rankers/r2", json=_RANKER_BODY)
        rankers = client.get("/screener/rankers").json()["rankers"]
        assert {r["ranker_id"] for r in rankers} == {"r1", "r2"}

    def test_malformed_body_is_422(self, client: TestClient) -> None:
        resp = client.put("/screener/rankers/r1", json={"universe": ["AAPL"], "factors": "not-a-list"})
        assert resp.status_code == 422

    def test_delete_removes_the_ranker(self, client: TestClient) -> None:
        client.put("/screener/rankers/r1", json=_RANKER_BODY)
        resp = client.delete("/screener/rankers/r1")
        assert resp.json()["deleted"] is True
        assert client.get("/screener/rankers/r1").status_code == 404

    def test_interval_below_floor_is_raised(self, client: TestClient) -> None:
        from vinu_screener.rankers.config import RANKER_MIN_INTERVAL_SEC

        client.put("/screener/rankers/r1", json={**_RANKER_BODY, "interval_sec": 1.0})
        assert client.get("/screener/rankers/r1").json()["interval_sec"] == RANKER_MIN_INTERVAL_SEC


class TestRankerEnableDisable:
    def test_disable_then_enable(self, client: TestClient) -> None:
        client.put("/screener/rankers/r1", json=_RANKER_BODY)
        d = client.post("/screener/rankers/r1/disable")
        assert d.json()["active"] is False
        e = client.post("/screener/rankers/r1/enable")
        assert e.json()["active"] is True

    def test_disable_unknown_ranker_is_404(self, client: TestClient) -> None:
        assert client.post("/screener/rankers/ghost/disable").status_code == 404


class TestRankOnDemand:
    def test_rank_now_returns_a_ranked_top(self, client: TestClient) -> None:
        client.put("/screener/rankers/r1", json=_RANKER_BODY)
        resp = client.post("/screener/rankers/r1/rank")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ranker_id"] == "r1"
        assert body["top"][0]["symbol"] == "AAPL"

    def test_rank_now_on_unknown_ranker_is_404(self, client: TestClient) -> None:
        assert client.post("/screener/rankers/ghost/rank").status_code == 404

    def test_latest_is_404_before_any_run(self, client: TestClient) -> None:
        client.put("/screener/rankers/r1", json=_RANKER_BODY)
        assert client.get("/screener/rankers/r1/latest").status_code == 404

    def test_latest_reflects_the_last_rank_now_call(self, client: TestClient) -> None:
        client.put("/screener/rankers/r1", json=_RANKER_BODY)
        client.post("/screener/rankers/r1/rank")
        resp = client.get("/screener/rankers/r1/latest")
        assert resp.status_code == 200
        assert resp.json()["top"][0]["symbol"] == "AAPL"
