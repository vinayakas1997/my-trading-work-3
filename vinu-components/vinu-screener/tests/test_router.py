from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_screener.serve.pairlist_cache import PairlistCache
from vinu_screener.serve.router import build_router


def _client(refresh_fn, *, token: str = "secret") -> TestClient:
    cache = PairlistCache(refresh_fn=refresh_fn, ttl_sec=60.0)
    app = FastAPI()
    app.include_router(build_router(cache, bearer_token=token))
    return TestClient(app)


class TestAuth:
    def test_missing_token_is_401(self) -> None:
        client = _client(lambda r: ["A"])
        resp = client.get("/screener/pairlist/r1")
        assert resp.status_code == 401

    def test_wrong_token_is_401(self) -> None:
        client = _client(lambda r: ["A"])
        resp = client.get("/screener/pairlist/r1", headers={"Authorization": "Bearer wrong"})
        assert resp.status_code == 401

    def test_correct_token_returns_pairlist(self) -> None:
        client = _client(lambda r: ["A", "B"])
        resp = client.get("/screener/pairlist/r1", headers={"Authorization": "Bearer secret"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["symbols"] == ["A", "B"]
        assert body["rule_id"] == "r1"
        assert body["stale"] is False


class TestFailOpenOverHttp:
    def test_no_cache_and_refresh_fails_is_503(self) -> None:
        def broken(rule_id: str) -> list[str]:
            raise ConnectionError("down")

        client = _client(broken)
        resp = client.get("/screener/pairlist/r1", headers={"Authorization": "Bearer secret"})
        assert resp.status_code == 503

    def test_stale_cache_is_still_served_as_200(self) -> None:
        state = {"fail": False}

        def refresh(rule_id: str) -> list[str]:
            if state["fail"]:
                raise ConnectionError("down")
            return ["A"]

        cache = PairlistCache(refresh_fn=refresh, ttl_sec=0.0)  # every call is past TTL
        app = FastAPI()
        app.include_router(build_router(cache, bearer_token="secret"))
        client = TestClient(app)

        r1 = client.get("/screener/pairlist/r1", headers={"Authorization": "Bearer secret"})
        assert r1.json()["stale"] is False

        state["fail"] = True
        r2 = client.get("/screener/pairlist/r1", headers={"Authorization": "Bearer secret"})
        assert r2.status_code == 200
        assert r2.json()["stale"] is True
        assert r2.json()["symbols"] == ["A"]
