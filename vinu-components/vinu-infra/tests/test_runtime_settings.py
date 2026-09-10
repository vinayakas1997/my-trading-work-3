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
