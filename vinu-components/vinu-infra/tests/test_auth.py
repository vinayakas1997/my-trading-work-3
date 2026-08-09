import importlib

import pytest
from fastapi import HTTPException, Request


def _make_request(headers: dict[str, str]) -> Request:
    encoded = [(k.lower().encode(), v.encode()) for k, v in headers.items()]
    scope = {"type": "http", "headers": encoded}
    return Request(scope)


@pytest.fixture
def auth_module(monkeypatch):
    monkeypatch.setenv("VINU_API_KEY", "real-secret-key")
    import vinu_infra.auth as auth
    importlib.reload(auth)  # module-level VINU_API_KEY is read at import time
    yield auth
    monkeypatch.delenv("VINU_API_KEY", raising=False)
    importlib.reload(auth)


@pytest.mark.asyncio
async def test_valid_bearer_token_passes(auth_module):
    req = _make_request({"Authorization": "Bearer real-secret-key"})
    await auth_module.require_auth(req)  # must not raise


@pytest.mark.asyncio
async def test_wrong_token_raises_403(auth_module):
    req = _make_request({"Authorization": "Bearer wrong-key"})
    with pytest.raises(HTTPException) as exc_info:
        await auth_module.require_auth(req)
    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_missing_header_raises_401(auth_module):
    req = _make_request({})
    with pytest.raises(HTTPException) as exc_info:
        await auth_module.require_auth(req)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_malformed_header_raises_401(auth_module):
    req = _make_request({"Authorization": "real-secret-key"})  # missing "Bearer " prefix
    with pytest.raises(HTTPException) as exc_info:
        await auth_module.require_auth(req)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_no_api_key_configured_allows_all_requests(monkeypatch):
    monkeypatch.delenv("VINU_API_KEY", raising=False)
    import vinu_infra.auth as auth
    importlib.reload(auth)
    req = _make_request({})
    await auth.require_auth(req)  # must not raise -- auth is opt-in
    importlib.reload(auth)
