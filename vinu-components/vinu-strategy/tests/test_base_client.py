"""item #22 finding #7: a shared threading.Lock() used to wrap every
HTTP call's full round-trip -- with FeaturesClient/CorrelationClient
each a single instance shared across service.py's _MAX_WORKERS=10
executor, concurrent symbol fetches were serialized through one call at
a time regardless of the thread pool. Previously zero dedicated test
coverage for this file at all."""

from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from vinu_strategy.clients.base import BaseClient


def _mock_response(status_code: int = 200, json_body=None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body if json_body is not None else {}
    if status_code >= 400:
        # Real httpx.Client.raise_for_status() always raises
        # HTTPStatusError (which carries `.response`), never the bare
        # HTTPError base class -- matching that exactly here, not a
        # looser mock that wouldn't reflect real httpx behavior.
        resp.raise_for_status.side_effect = httpx.HTTPStatusError(
            f"HTTP {status_code}", request=MagicMock(), response=resp,
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


class TestBaseClientRequestBasics:
    def test_successful_get_returns_parsed_json(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.get = MagicMock(return_value=_mock_response(json_body={"ok": True}))
        assert client._get("/x") == {"ok": True}

    def test_successful_post_returns_parsed_json(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.post = MagicMock(return_value=_mock_response(json_body={"created": True}))
        assert client._post("/x", json={"a": 1}) == {"created": True}

    def test_transient_status_retries_then_succeeds(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.get = MagicMock(
            side_effect=[_mock_response(503), _mock_response(json_body={"ok": True})]
        )
        with patch("time.sleep"):
            result = client._get("/x")
        assert result == {"ok": True}
        assert client._client.get.call_count == 2

    def test_exhausts_retries_and_returns_empty_dict(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.get = MagicMock(return_value=_mock_response(503))
        with patch("time.sleep"):
            result = client._get("/x")
        assert result == {}
        assert client._client.get.call_count == 3

    def test_timeout_retries_then_succeeds(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.get = MagicMock(
            side_effect=[httpx.TimeoutException("slow"), _mock_response(json_body={"ok": True})]
        )
        with patch("time.sleep"):
            result = client._get("/x")
        assert result == {"ok": True}

    def test_non_transient_http_error_returns_empty_dict_no_retry(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.get = MagicMock(return_value=_mock_response(404))
        result = client._get("/x")
        assert result == {}
        assert client._client.get.call_count == 1

    def test_unexpected_exception_returns_empty_dict(self) -> None:
        client = BaseClient("http://fake-service")
        client._client.get = MagicMock(side_effect=ValueError("boom"))
        assert client._get("/x") == {}


class TestBaseClientConcurrency:
    """The actual fix: concurrent callers on one shared BaseClient
    instance must not be serialized through a lock around the network
    call."""

    def test_concurrent_requests_run_in_parallel_not_serialized(self) -> None:
        client = BaseClient("http://fake-service")
        sleep_seconds = 0.2
        n_workers = 5

        def _slow_get(url, **kwargs):
            time.sleep(sleep_seconds)
            return _mock_response(json_body={"ok": True})

        client._client.get = _slow_get

        start = time.monotonic()
        threads = [threading.Thread(target=client._get, args=("/x",)) for _ in range(n_workers)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        elapsed = time.monotonic() - start

        # Serialized (the old lock-around-the-call behavior) would take
        # roughly n_workers * sleep_seconds (1.0s here). Truly concurrent
        # takes roughly one sleep_seconds regardless of n_workers. A
        # generous ceiling well below the serialized total, to avoid
        # flaking on a loaded CI box while still failing hard if the lock
        # ever comes back.
        assert elapsed < sleep_seconds * (n_workers / 2)

    def test_no_lock_attribute_left_on_the_instance(self) -> None:
        """Regression guard for the fix itself, not just its effect."""
        client = BaseClient("http://fake-service")
        assert not hasattr(client, "_lock")
