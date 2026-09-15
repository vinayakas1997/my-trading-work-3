"""Task 11 (service auth): vinu-live builds its FastAPI app directly
(not via vinu_infra.server.create_app), so the shared opt-in bearer-token
auth was the one layer it bypassed. These tests pin the required behavior:
reject unauthenticated, accept authenticated, and stay open when no key is
configured (auth is opt-in).

/live/status (not /live/health) is used: vinu_infra.auth.require_auth
deliberately exempts every path ending in "/health" unconditionally
(Docker healthchecks must stay reachable with no credentials -- see
auth.py's own comment), so a /health route can no longer exercise real
auth behavior at all -- it always returns 200 regardless of key/token,
which silently broke this file's original intent of testing rejection/
acceptance through require_auth. /live/status has the same "no service
backend" property /health was chosen for, without being exempt.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

import vinu_infra.auth as auth_mod
from vinu_live.server.app import create_app

AUTH_HEADER = {"Authorization": "Bearer test-secret"}


def test_unauthenticated_request_rejected_when_key_set(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "test-secret")
    client = TestClient(create_app())
    resp = client.get("/live/status")
    assert resp.status_code == 401
    assert resp.headers.get("WWW-Authenticate") == "Bearer"


def test_wrong_token_rejected_when_key_set(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "test-secret")
    client = TestClient(create_app())
    resp = client.get("/live/status", headers={"Authorization": "Bearer wrong-key"})
    assert resp.status_code == 403


def test_authenticated_request_accepted_when_key_set(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "test-secret")
    client = TestClient(create_app())
    resp = client.get("/live/status", headers=AUTH_HEADER)
    assert resp.status_code == 200


def test_route_open_when_no_key_configured(monkeypatch) -> None:
    monkeypatch.setattr(auth_mod, "VINU_API_KEY", "")
    client = TestClient(create_app())
    resp = client.get("/live/status")
    assert resp.status_code == 200


def test_health_route_is_always_open_regardless_of_key() -> None:
    """Pins the deliberate exemption itself (auth.py's own documented
    behavior for Docker/orchestrator healthchecks) so a future change to
    that exemption is caught here, in the same file as the tests it
    affects, rather than only implicitly relied upon above."""
    client = TestClient(create_app())
    resp = client.get("/live/health")
    assert resp.status_code == 200