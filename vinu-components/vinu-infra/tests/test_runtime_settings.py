import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from vinu_infra.runtime_settings import RuntimeSettings, build_admin_settings_router


def _settings() -> RuntimeSettings:
    s = RuntimeSettings()
    s.register("max_order_value", default=50000.0, minimum=0.0,
               description="Max notional value of a single order.")
    s.register("max_daily_orders", default=10, caster=int, minimum=0,
               description="Max orders per symbol per day.")
    return s


def _client(router: APIRouter) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


class TestRuntimeSettingsCore:
    def test_get_set_reset_roundtrip(self) -> None:
        s = _settings()
        assert s.get("max_order_value") == 50000.0
        assert s.set("max_order_value", "12345") == 12345.0
        assert s.get("max_order_value") == 12345.0
        assert s.reset("max_order_value") == 50000.0
        assert s.get("max_order_value") == 50000.0

    def test_set_rejects_out_of_range(self) -> None:
        s = _settings()
        try:
            s.set("max_daily_orders", -1)
        except ValueError as exc:
            assert "max_daily_orders" in str(exc)
        else:
            raise AssertionError("expected ValueError")


class TestVersioning:
    """Stage A (A32): optimistic-concurrency token so two operators editing
    the admin API don't silently clobber each other."""

    def test_version_bumps_only_on_an_effective_change(self) -> None:
        s = _settings()
        assert s.version == 0
        s.set("max_order_value", 111.0)
        assert s.version == 1
        s.set("max_order_value", 111.0)  # same value -> no bump
        assert s.version == 1
        s.reset("max_order_value")
        assert s.version == 2
        s.reset("max_order_value")  # nothing to drop -> no bump
        assert s.version == 2

    def test_check_version_raises_on_mismatch(self) -> None:
        s = _settings()
        s.check_version(0)  # ok
        s.set("max_order_value", 5.0)
        with pytest.raises(ValueError, match="version mismatch"):
            s.check_version(0)

    def test_get_returns_version_and_settings(self) -> None:
        router = build_admin_settings_router(_settings())
        body = _client(router).get("/admin/settings").json()
        assert body["version"] == 0
        assert "max_order_value" in body["settings"]

    def test_patch_with_stale_if_match_is_409(self) -> None:
        router = build_admin_settings_router(_settings())
        client = _client(router)
        client.patch("/admin/settings", json={"max_order_value": 20000})  # version -> 1
        resp = client.patch(
            "/admin/settings", json={"max_order_value": 30000}, headers={"If-Match": "0"},
        )
        assert resp.status_code == 409

    def test_patch_with_current_if_match_succeeds_and_returns_new_version(self) -> None:
        router = build_admin_settings_router(_settings())
        client = _client(router)
        v = client.get("/admin/settings").json()["version"]
        resp = client.patch(
            "/admin/settings", json={"max_order_value": 20000}, headers={"If-Match": str(v)},
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == v + 1

    def test_patch_without_if_match_still_works(self) -> None:
        router = build_admin_settings_router(_settings())
        resp = _client(router).patch("/admin/settings", json={"max_order_value": 20000})
        assert resp.status_code == 200

    def test_non_integer_if_match_is_400(self) -> None:
        router = build_admin_settings_router(_settings())
        resp = _client(router).patch(
            "/admin/settings", json={"max_order_value": 1}, headers={"If-Match": "abc"},
        )
        assert resp.status_code == 400


class TestOnChangeAudit:
    """Stage A (A21): every mutation through the admin router calls the
    injected on_change callback -- how a service records a runtime risk-
    limit change into its own audit trail."""

    def test_patch_fires_on_change_with_applied_values(self) -> None:
        seen: list[tuple[str, dict]] = []
        router = build_admin_settings_router(
            _settings(), on_change=lambda action, changes: seen.append((action, changes)),
        )
        resp = _client(router).patch("/admin/settings", json={"max_order_value": 20000})
        assert resp.status_code == 200
        assert seen == [("set", {"max_order_value": 20000.0})]

    def test_reset_fires_on_change(self) -> None:
        seen: list[tuple[str, dict]] = []
        router = build_admin_settings_router(
            _settings(), on_change=lambda action, changes: seen.append((action, changes)),
        )
        client = _client(router)
        client.patch("/admin/settings", json={"max_order_value": 20000})
        seen.clear()
        resp = client.post("/admin/settings/max_order_value/reset")
        assert resp.status_code == 200
        assert seen == [("reset", {"max_order_value": 50000.0})]

    def test_rejected_patch_does_not_fire_on_change(self) -> None:
        seen: list = []
        router = build_admin_settings_router(
            _settings(), on_change=lambda action, changes: seen.append((action, changes)),
        )
        resp = _client(router).patch("/admin/settings", json={"no_such_knob": 1})
        assert resp.status_code == 422
        assert seen == []

    def test_on_change_exception_does_not_fail_the_request(self) -> None:
        def _boom(action, changes):
            raise RuntimeError("audit sink down")

        router = build_admin_settings_router(_settings(), on_change=_boom)
        resp = _client(router).patch("/admin/settings", json={"max_order_value": 20000})
        assert resp.status_code == 200
        assert resp.json()["updated"] == {"max_order_value": 20000.0}

    def test_no_callback_is_fine(self) -> None:
        router = build_admin_settings_router(_settings())
        resp = _client(router).patch("/admin/settings", json={"max_order_value": 20000})
        assert resp.status_code == 200
