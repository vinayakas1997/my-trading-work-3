"""GET /analysis/angles?active=true lists only the angles that will actually run under the current model policy, so a coverage
check ("does every angle have data?") counts the right set. Default (no param) still lists every discovered angle."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_initial_analysis.server import routes_read


def _angle(name, category):
    return {"name": name, "title": name, "purpose": "", "spec": {"category": category}}


ANGLES = [_angle("arima", "raw_data"), _angle("chronos", "model"), _angle("lstm", "model"),
          _angle("moirai", "disabled"), _angle("regime_analysis", "raw_data")]


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes_read, "get_service", lambda: SimpleNamespace(list_angles=lambda: ANGLES))
    app = FastAPI()
    app.include_router(routes_read.router, prefix="/analysis")
    return TestClient(app)


def _names(resp):
    return [a["name"] for a in resp.json()["angles"]]


def test_default_lists_every_discovered_angle(client):
    assert _names(client.get("/analysis/angles")) == ["arima", "chronos", "lstm", "moirai", "regime_analysis"]


def test_active_with_models_on_drops_only_the_permanently_disabled(client, monkeypatch):
    import vinu_infra.system_manifest as sm

    monkeypatch.setattr(sm, "models_enabled", lambda: True)
    assert _names(client.get("/analysis/angles", params={"active": "true"})) == ["arima", "chronos", "lstm", "regime_analysis"]


def test_active_with_models_off_also_drops_the_model_angles(client, monkeypatch):
    import vinu_infra.system_manifest as sm

    monkeypatch.setattr(sm, "models_enabled", lambda: False)
    assert _names(client.get("/analysis/angles", params={"active": "true"})) == ["arima", "regime_analysis"]
