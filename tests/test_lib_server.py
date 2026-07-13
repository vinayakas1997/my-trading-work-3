from fastapi.testclient import TestClient
from fastapi import APIRouter

from vinu_lib.server import create_app


def test_create_app_health():
    router = APIRouter()
    app = create_app("test-svc", "1.0", "test", router)
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert data["service"] == "test-svc"
    assert data["version"] == "1.0"


def test_create_app_router():
    router = APIRouter()

    @router.get("/ping")
    def ping():
        return {"pong": True}

    app = create_app("test-svc", "1.0", "test", router)
    client = TestClient(app)
    resp = client.get("/ping")
    assert resp.status_code == 200
    assert resp.json() == {"pong": True}


def test_create_app_validation_error():
    router = APIRouter()

    @router.get("/fail")
    def fail():
        raise ValueError("bad input")

    app = create_app("test-svc", "1.0", "test", router)
    client = TestClient(app)
    resp = client.get("/fail")
    assert resp.status_code == 422
    assert "bad input" in resp.text


def test_create_app_config_routes():
    config_router = APIRouter()

    @config_router.get("/settings")
    def settings():
        return {"foo": "bar"}

    app = create_app("test-svc", "1.0", "test", APIRouter(), config_routes=config_router)
    client = TestClient(app)
    resp = client.get("/settings")
    assert resp.status_code == 200
    assert resp.json() == {"foo": "bar"}
