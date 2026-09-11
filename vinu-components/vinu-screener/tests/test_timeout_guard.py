from __future__ import annotations

import time

from vinu_screener.scan.timeout_guard import call_with_timeout


class TestCallWithTimeout:
    def test_fast_call_succeeds(self) -> None:
        result = call_with_timeout(lambda: 42, timeout_sec=1.0)
        assert result.ok is True
        assert result.value == 42
        assert result.timed_out is False

    def test_slow_call_times_out(self) -> None:
        def _slow():
            time.sleep(0.5)
            return "too late"

        result = call_with_timeout(_slow, timeout_sec=0.05)
        assert result.ok is False
        assert result.timed_out is True
        assert result.value is None

    def test_exception_is_reported_not_raised(self) -> None:
        def _boom():
            raise RuntimeError("upstream is down")

        result = call_with_timeout(_boom, timeout_sec=1.0)
        assert result.ok is False
        assert result.timed_out is False
        assert "upstream is down" in result.error

    def test_args_and_kwargs_are_forwarded(self) -> None:
        result = call_with_timeout(lambda a, b, c=0: a + b + c, 1, 2, c=3, timeout_sec=1.0)
        assert result.value == 6

    def test_latency_is_measured(self) -> None:
        result = call_with_timeout(lambda: time.sleep(0.02), timeout_sec=1.0)
        assert result.latency_ms >= 15.0
