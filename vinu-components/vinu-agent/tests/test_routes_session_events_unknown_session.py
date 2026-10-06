"""GET /sessions/{id}/events used to hold a stream open forever for a session that does not exist, which hung any
client (and a full API sweep) polling a wrong id. It must answer 404 immediately, like the other session routes."""
from __future__ import annotations

from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from vinu_agent.server import routes_sessions


class _Store:
    def __init__(self, known: set[str]) -> None:
        self._known = known

    def get_session(self, session_id: str):
        return SimpleNamespace(session_id=session_id) if session_id in self._known else None


class _Bus:
    async def subscribe(self, session_id, last_event_id):
        if False:
            yield  # a real session streams events; this one ends at once


def _client(known: set[str]) -> TestClient:
    app = FastAPI()
    app.include_router(routes_sessions.router)
    routes_sessions._get_service = lambda: SimpleNamespace(_store=_Store(known), event_bus=_Bus())
    return TestClient(app)


def test_unknown_session_events_is_404_not_a_hang():
    resp = _client(set()).get("/sessions/does-not-exist/events")
    assert resp.status_code == 404


def test_known_session_still_streams():
    resp = _client({"s1"}).get("/sessions/s1/events")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/event-stream")
