"""item #13 finding #6 (system-wide-audit-and-design/
02-open-questions-strategy-and-simulation.md): `clients/base.py` had zero
dedicated tests -- the retry/backoff loop and its thread-local client
model were only ever exercised indirectly through subclasses.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vinu_simulator.clients.base import BaseClient


def _mock_response(status_code: int = 200, json_body=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    if status_code >= 400:
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestRequestBasics:
    def test_successful_get_returns_parsed_json(self) -> None:
        client = BaseClient("http://fake-service")
        client._client().get = MagicMock(return_value=_mock_response(json_body={"ok": True}))
        assert client.get("/x") == {"ok": True}

    def test_successful_post_returns_parsed_json(self) -> None:
        client = BaseClient("http://fake-service")
        client._client().post = MagicMock(return_value=_mock_response(json_body={"created": True}))
        assert client.post("/x", json={"a": 1}) == {"created": True}

    def test_transient_status_retries_then_succeeds(self) -> None:
        client = BaseClient("http://fake-service")
        client._client().get = MagicMock(
            side_effect=[_mock_response(503), _mock_response(json_body={"ok": True})]
        )
        with patch("time.sleep"):
            result = client.get("/x")
        assert result == {"ok": True}
        assert client._client().get.call_count == 2

    def test_timeout_retries_then_succeeds(self) -> None:
        client = BaseClient("http://fake-service")
        client._client().get = MagicMock(
            side_effect=[httpx.TimeoutException("slow"), _mock_response(json_body={"ok": True})]
        )
        with patch("time.sleep"):
            result = client.get("/x")
        assert result == {"ok": True}

    def test_retries_exhausted_reraises_instead_of_swallowing(self) -> None:
        """Unlike vinu-strategy's BaseClient, this one re-raises on
        exhaustion rather than returning an empty dict -- callers
        (price_client.py's per-symbol `_fetch`) rely on this to
        distinguish "fetch failed" from "fetch succeeded with an empty
        body" via their own `except Exception` at the call site."""
        client = BaseClient("http://fake-service")
        client._client().get = MagicMock(return_value=_mock_response(503))
        with patch("time.sleep"), pytest.raises(Exception):
            client.get("/x")
        assert client._client().get.call_count == 3

    def test_non_transient_http_error_propagates_not_swallowed(self) -> None:
        client = BaseClient("http://fake-service")
        client._client().get = MagicMock(return_value=_mock_response(404))
        with pytest.raises(httpx.HTTPStatusError):
            client.get("/x")
        assert client._client().get.call_count == 1


class TestThreadLocalClient:
    def test_each_thread_gets_its_own_httpx_client(self) -> None:
        """The actual design this file uses instead of a shared lock
        (contrast vinu-strategy's item #22 finding #7 fix, which dropped
        a lock around one shared client) -- confirms it really is
        per-thread, not accidentally shared."""
        client = BaseClient("http://fake-service")
        seen: dict[int, int] = {}

        def _record() -> None:
            seen[threading.get_ident()] = id(client._client())

        threads = [threading.Thread(target=_record) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(set(seen.values())) == 4

    def test_close_only_closes_the_calling_threads_client(self) -> None:
        client = BaseClient("http://fake-service")
        this_thread_client = client._client()
        this_thread_client.close = MagicMock()

        other_client_closed = []

        def _other_thread() -> None:
            c = client._client()
            c.close = lambda: other_client_closed.append(True)

        t = threading.Thread(target=_other_thread)
        t.start()
        t.join()

        client.close()
        this_thread_client.close.assert_called_once()
        assert other_client_closed == []
