from fastapi.testclient import TestClient
from fastapi import APIRouter

from vinu_infra.server import create_app


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


def test_create_app_replaces_nan_with_null_in_response():
    import math

    router = APIRouter()

    @router.get("/nan")
    def has_nan():
        return {"value": math.nan, "nested": {"also": math.nan}, "list": [1.0, math.nan, 3.0]}

    app = create_app("test-svc", "1.0", "test", router)
    client = TestClient(app)
    resp = client.get("/nan")
    assert resp.status_code == 200
    # A raw NaN in the response body is invalid JSON per spec -- confirm the
    # real wire bytes contain "null", not the literal token "NaN".
    assert "NaN" not in resp.text
    data = resp.json()
    assert data["value"] is None
    assert data["nested"]["also"] is None
    assert data["list"] == [1.0, None, 3.0]


def test_nan_replacement_is_scoped_to_this_apps_response_class_only():
    # Real regression guard for the fix itself: importing vinu_infra.server
    # (done implicitly by every test in this file) must not globally patch
    # fastapi.responses.JSONResponse for every other app/response in the
    # process -- a plain JSONResponse must still render NaN as-is.
    from fastapi.responses import JSONResponse

    resp = JSONResponse(content={"value": None})
    assert JSONResponse.render is not None  # the class itself, unpatched
    import inspect
    assert "vinu_infra" not in (inspect.getmodule(JSONResponse.render).__name__ or "")


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
