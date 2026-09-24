from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import pytest

from vinu_initial_analysis.angles.signal_evidence.compute import (
    ANGLE_NAME,
    MUST_CONDITION_NAME,
    compute,
)


def _make_flat_bars(n: int) -> pd.DataFrame:
    close = np.full(n, 100.0)
    bar_ts = (pd.date_range("2024-01-01", periods=n, freq="15min").astype("int64") // 10**9).astype(int)
    return pd.DataFrame({
        "bar_ts": bar_ts, "open": close, "high": close + 0.1, "low": close - 0.1,
        "close": close, "volume": np.full(n, 1_000_000.0),
    })


def _make_bars_with_crossing(n: int = 150, flat_len: int = 60) -> pd.DataFrame:
    """Deterministic (no randomness): a very slow, strictly monotonic
    decline for `flat_len` bars (SMA5 stays a hair below SMA50 the whole
    time -- a 5-bar average of a declining series always sits closer to
    the more-recent, lower values than a 50-bar average does -- so no
    spurious crossing occurs there; a nonzero, non-degenerate true range
    throughout, unlike a mathematically-exact-flat series, gives ADX real
    input to compute on), then a much steeper, strictly increasing linear
    ramp for the rest. SMA(5) reacts to the ramp far faster than SMA(50),
    so there is exactly one, well-defined SMA5-crosses-above-SMA50 event,
    well after both SMAs have real (non-NaN) values, with a clean,
    monotonic uptrend following it -- the outcome math is then
    unambiguous, not a coin flip on noise."""
    flat = 100.0 - np.arange(flat_len) * 0.01
    ramp = flat[-1] + np.arange(1, n - flat_len + 1) * 0.5
    close = np.concatenate([flat, ramp])
    high = close + 0.3
    low = close - 0.3
    open_ = close - 0.05
    volume = np.linspace(1_000_000, 1_500_000, n)
    bar_ts = (pd.date_range("2024-01-01", periods=n, freq="15min").astype("int64") // 10**9).astype(int)
    return pd.DataFrame({
        "bar_ts": bar_ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume,
    })


def _first_crossing_index(bars: pd.DataFrame) -> int:
    from vinu_initial_analysis.angles.signal_evidence.compute import SMA_FAST, SMA_SLOW, _find_crossings, _sma

    close = bars["close"].astype(float)
    crossings = _find_crossings(_sma(close, SMA_FAST), _sma(close, SMA_SLOW))
    assert crossings, "test fixture must produce at least one crossing"
    return crossings[0]


class _FakeResponse:
    def __init__(self, status_code: int) -> None:
        self.status_code = status_code


class _FakeClient:
    """Records every POST it receives; status codes are scripted per-path
    via `responses`, defaulting to 200."""

    calls: list[tuple[str, dict[str, Any]]] = []
    responses: dict[str, int] = {}

    def __init__(self, *args, **kwargs) -> None:
        pass

    def __enter__(self) -> "_FakeClient":
        return self

    def __exit__(self, *args) -> None:
        return None

    def post(self, url: str, json: dict[str, Any], timeout: float) -> _FakeResponse:
        type(self).calls.append((url, json))
        status = 200
        for path_fragment, code in type(self).responses.items():
            if path_fragment in url:
                status = code
        return _FakeResponse(status)


@pytest.fixture(autouse=True)
def _patch_httpx(monkeypatch):
    import httpx

    _FakeClient.calls = []
    _FakeClient.responses = {}
    monkeypatch.setattr(httpx, "Client", _FakeClient)
    yield
    monkeypatch.undo()


class TestComputeGating:
    def test_no_data_returns_status_no_data(self):
        df = compute("AAPL", bars=None)
        assert df.iloc[0]["status"] == "no_data"
        assert df.iloc[0]["angle"] == ANGLE_NAME

    def test_insufficient_data_status(self):
        df = compute("AAPL", bars=_make_flat_bars(20))
        assert df.iloc[0]["status"] == "insufficient_data"


class TestCrossingDetectionAndRecording:
    def test_finds_the_engineered_crossing_and_records_it(self):
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, time_format="15min")
        row = df.iloc[0]
        assert row["status"] == "ok"
        assert row["must_condition"] == MUST_CONDITION_NAME
        assert row["crossings_found"] >= 1
        assert row["triggers_recorded"] >= 1
        assert row["triggers_record_errors"] == 0

        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        outcome_calls = [c for c in _FakeClient.calls if "/outcome" in c[0]]
        assert len(trigger_calls) == len(outcome_calls) == row["triggers_recorded"]

        payload = trigger_calls[0][1]
        assert payload["symbol"] == "AAPL"
        assert payload["must_condition"] == MUST_CONDITION_NAME
        assert payload["granularity"] == "15min"
        assert "adx" in payload["indicators"]
        assert "rsi" in payload["indicators"]
        assert "volume_vs_avg20" in payload["indicators"]
        assert "policy_version" in payload

    def test_flat_series_finds_no_crossing(self):
        df = compute("AAPL", bars=_make_flat_bars(150))
        assert df.iloc[0]["crossings_found"] == 0
        assert df.iloc[0]["triggers_recorded"] == 0
        assert _FakeClient.calls == []

    def test_crossing_too_close_to_window_end_is_skipped_not_errored(self):
        """A crossing near the very end of the provided bars can't have its
        forward outcome measured yet -- must be skipped honestly, not
        treated as a failure (Decision 1: the outcome is recorded once the
        horizon has actually elapsed, never fabricated)."""
        full_bars = _make_bars_with_crossing(n=150)
        crossing_idx = _first_crossing_index(full_bars)
        # Leave only a handful of bars after the crossing -- well short
        # of the angle's FORWARD_HORIZON_BARS (20), so its outcome can't
        # be measured yet within this truncated window. Still long enough
        # in total to clear MIN_OBSERVATIONS.
        from vinu_initial_analysis.angles.signal_evidence.compute import MIN_OBSERVATIONS

        cutoff = max(crossing_idx + 6, MIN_OBSERVATIONS + 1)
        assert cutoff < crossing_idx + 20, "fixture must still leave the horizon incomplete"
        truncated = full_bars.iloc[:cutoff].reset_index(drop=True)

        df = compute("AAPL", bars=truncated)
        row = df.iloc[0]
        assert row["crossings_found"] >= 1
        assert row["triggers_recorded"] == 0
        assert row["triggers_skipped_incomplete_horizon"] == row["crossings_found"]
        assert _FakeClient.calls == []

    def test_duplicate_trigger_counted_as_already_recorded_not_error(self):
        _FakeClient.responses = {"/trigger": 409}
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars)
        row = df.iloc[0]
        assert row["triggers_already_recorded"] >= 1
        assert row["triggers_recorded"] == 0
        assert row["triggers_record_errors"] == 0
        # A 409 on the trigger POST means no outcome POST should follow it
        outcome_calls = [c for c in _FakeClient.calls if "/outcome" in c[0]]
        assert outcome_calls == []

    def test_http_failure_on_trigger_counted_as_record_error(self):
        _FakeClient.responses = {"/trigger": 500}
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars)
        row = df.iloc[0]
        assert row["triggers_record_errors"] >= 1
        assert row["triggers_recorded"] == 0

    def test_outcome_values_are_computed_from_real_forward_prices(self):
        bars = _make_bars_with_crossing()
        compute("AAPL", bars=bars)
        outcome_calls = [c for c in _FakeClient.calls if "/outcome" in c[0]]
        assert outcome_calls
        payload = outcome_calls[0][1]
        # This is an engineered uptrend after the crossing -- the forward
        # return and max favorable excursion should both be positive.
        assert payload["return_at_horizon"] > 0
        assert payload["max_favorable_excursion"] >= payload["return_at_horizon"] - 1e-9
        assert payload["max_adverse_excursion"] <= payload["return_at_horizon"] + 1e-9
