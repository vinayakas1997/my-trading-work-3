"""Task 11 (service auth): vinu-portfolio builds its FastAPI app directly
(not via vinu_infra.server.create_app), so the shared opt-in bearer-token
auth was the one layer it bypassed. These tests pin the required behavior:
reject unauthenticated, accept authenticated, and stay open when no key is
configured (auth is opt-in). /portfolio/health is used because it is the one
route that never touches PortfolioService, so the auth assertion is isolated
from any data dependency.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import vinu_infra.auth as auth_mod
from vinu_portfolio.server.app import create_app

AUTH_HEADER = {"Authorization": "Bearer test-secret"}


def test_unauthenticated_request_rejected_when_key_set(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "test-secret")
    client = TestClient(create_app())
    resp = client.get("/portfolio/health")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_wrong_token_rejected_when_key_set(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "test-secret")
    client = TestClient(create_app())
    resp = client.get("/portfolio/health", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 403


def test_authenticated_request_accepted_when_key_set(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "test-secret")
    client = TestClient(create_app())
    resp = client.get("/portfolio/health", headers=AUTH_HEADER)
    assert resp.status_code == 200


def test_route_open_when_no_key_configured(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "")
    client = TestClient(create_app())
    resp = client.get("/portfolio/health")
    assert resp.status_code == 200