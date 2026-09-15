import asyncio
from types import SimpleNamespace

import pytest

from vinu_infra.llm.retry import (
    LlmCallFailed,
    LlmParseError,
    _retry_after_seconds,
    build_async_retry,
    build_retry,
)


class _ConnectionError(Exception):
    pass


class _UnrelatedError(Exception):
    pass


def _config(retry_max: int = 3) -> int:
    return retry_max


def _always_retry(exc: BaseException) -> bool:
    return isinstance(exc, (_ConnectionError, LlmParseError))


class TestBuildRetrySync:
    def test_succeeds_on_first_try_no_retries(self):
        calls = []

        def fn():
            calls.append(1)
            return "ok"

        retryer = build_retry(_config(), _always_retry)
        assert retryer(fn) == "ok"
        assert len(calls) == 1

    def test_retries_transient_failure_then_succeeds(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)
        attempts = {"n": 0}

        def fn():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _ConnectionError("boom")
            return "recovered"

        retryer = build_retry(_config(retry_max=5), _always_retry)
        assert retryer(fn) == "recovered"
        assert attempts["n"] == 3

    def test_gives_up_after_retry_max_and_reraises_original_exception(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)

        def fn():
            raise _ConnectionError("always fails")

        retryer = build_retry(_config(retry_max=3), _always_retry)
        with pytest.raises(_ConnectionError):
            retryer(fn)

    def test_non_retryable_exception_is_not_retried(self):
        calls = []

        def fn():
            calls.append(1)
            raise _UnrelatedError("not our problem")

        retryer = build_retry(_config(retry_max=5), _always_retry)
        with pytest.raises(_UnrelatedError):
            retryer(fn)
        assert len(calls) == 1  # no retry attempted

    def test_llm_parse_error_is_retried(self, monkeypatch):
        monkeypatch.setattr("time.sleep", lambda *_: None)
        attempts = {"n": 0}

        def fn():
            attempts["n"] += 1
            if attempts["n"] < 2:
                raise LlmParseError("bad json")
            return {"ok": True}

        retryer = build_retry(_config(retry_max=3), _always_retry)
        assert retryer(fn) == {"ok": True}
        assert attempts["n"] == 2


class TestBuildRetryAsync:
    def test_succeeds_on_first_try(self):
        async def fn():
            return "ok"

        async def run():
            retryer = build_async_retry(_config(), _always_retry)
            return await retryer(fn)

        assert asyncio.run(run()) == "ok"

    def test_retries_then_succeeds(self, monkeypatch):
        _real_sleep = asyncio.sleep
        monkeypatch.setattr("asyncio.sleep", lambda *_: _real_sleep(0))
        attempts = {"n": 0}

        async def fn():
            attempts["n"] += 1
            if attempts["n"] < 3:
                raise _ConnectionError("boom")
            return "recovered"

        async def run():
            retryer = build_async_retry(_config(retry_max=5), _always_retry)
            return await retryer(fn)

        assert asyncio.run(run()) == "recovered"
        assert attempts["n"] == 3


class TestRetryAfterExtraction:
    def test_extracts_retry_after_from_response_headers(self):
        exc = SimpleNamespace(response=SimpleNamespace(headers={"retry-after": "5"}))
        assert _retry_after_seconds(exc) == 5.0

    def test_none_when_no_response_attribute(self):
        assert _retry_after_seconds(_ConnectionError("x")) is None

    def test_none_when_header_missing(self):
        exc = SimpleNamespace(response=SimpleNamespace(headers={}))
        assert _retry_after_seconds(exc) is None

    def test_none_when_header_is_not_numeric(self):
        exc = SimpleNamespace(response=SimpleNamespace(headers={"retry-after": "not-a-number"}))
        assert _retry_after_seconds(exc) is None


def test_retry_logs_a_warning_before_each_sleep(monkeypatch, caplog):
    """The hand-rolled loops this module replaces logged a warning before
    every retry sleep -- losing that operational visibility would be a
    regression, not a cleanup."""
    import logging as _logging

    monkeypatch.setattr("time.sleep", lambda *_: None)
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise _ConnectionError("boom")
        return "ok"

    with caplog.at_level(_logging.WARNING, logger="vinu_infra.llm.retry"):
        retryer = build_retry(3, _always_retry)
        assert retryer(fn) == "ok"

    assert any("retrying in" in r.message for r in caplog.records)


def test_llm_call_failed_carries_last_error():
    original = _ConnectionError("root cause")
    failed = LlmCallFailed("gave up", last_error=original)
    assert failed.last_error is original
    assert "gave up" in str(failed)
