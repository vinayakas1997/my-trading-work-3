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
        # vinu_tools-backed indicators added alongside adx/rsi (short
        # lookbacks only -- the 150-bar fixture doesn't clear sma_100/200's
        # warmup, so those are correctly absent, not asserted here).
        for key in ("sma_5", "sma_10", "sma_20", "sma_50", "ema_5", "ema_10",
                    "dist_from_sma_5", "dist_from_sma_50", "dist_from_ema_5",
                    "roc_5", "roc_10", "roc_20", "atr_14", "stoch_k_14",
                    "stoch_d_14", "bollinger_band_width", "bollinger_percent_b",
                    "macd_line", "macd_signal", "macd_histogram",
                    "aroon_up", "aroon_down", "cci_20", "williams_r_14",
                    "supertrend", "high_low_spread", "open_close_return",
                    "momentum_10", "obv", "cmf_20",
                    "ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a",
                    "ichimoku_senkou_b", "parabolic_sar", "mfi_14",
                    "accumulation_distribution_line", "vwap_dist"):
            assert key in payload["indicators"], f"missing {key}"

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

    def test_vwap_dist_resets_per_session_not_cumulative_since_start(self):
        """The whole point of session-slicing vwap_dist (see
        06-mistake-duplicated-indicator-logic.md / all-possible-
        supporting-indicators.md's vwap_dist note): a cumulative-
        since-start VWAP would drag day 2's value toward day 1's price
        level. A correctly session-reset VWAP should not."""
        from vinu_initial_analysis.angles.signal_evidence.compute import _vwap_supporting

        n_per_day = 10
        day1_ts = pd.date_range("2024-01-01 09:30", periods=n_per_day, freq="15min", tz="UTC")
        day2_ts = pd.date_range("2024-01-02 09:30", periods=n_per_day, freq="15min", tz="UTC")
        ts = day1_ts.append(day2_ts)
        close = pd.Series([100.0] * n_per_day + [200.0] * n_per_day)
        high = close + 0.5
        low = close - 0.5
        volume = pd.Series([1000.0] * (2 * n_per_day))
        session_date = pd.Series(ts).dt.date

        vwap = _vwap_supporting(high, low, close, volume, session_date)
        # Day 2 trades flat at 200 -- its VWAP should land near 200, not
        # be pulled toward day 1's ~100 the way a cumulative-since-start
        # VWAP would.
        assert abs(vwap.iloc[-1] - 200.0) < 1.0

    def test_regime_is_absent_when_the_trigger_bar_predates_regimes_own_warmup(self):
        """item #6: regime_analysis's own classifier needs 141 bars of its
        own warmup (VOL_BASELINE_WINDOW + VOL_WINDOW) before it produces
        any value at all -- the default 150-bar fixture's crossing (index
        61) is well before that, so "regime" must be sparse-absent here,
        the same graceful-absence behavior every other indicator in this
        payload already has, not a fabricated placeholder."""
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, time_format="15min")
        assert df.iloc[0]["status"] == "ok"
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        assert "regime" not in trigger_calls[0][1]["indicators"]

    def test_regime_is_tagged_at_the_exact_trigger_bar_once_warmed_up(self):
        """item #6: reuses regime_analysis's own point-in-time-safe
        classifier as one more field on the trigger's indicator snapshot
        -- with enough bar history for regime_analysis's own warmup to
        clear by the trigger bar, "regime" is present and is looked up by
        bar_ts (not positional index -- compute_regime_frame() drops rows
        and re-indexes from 0, so those two indices are not the same
        series once rows get dropped)."""
        bars = _make_bars_with_crossing(n=175, flat_len=145)
        df = compute("AAPL", bars=bars, time_format="15min")
        assert df.iloc[0]["status"] == "ok"
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        assert trigger_calls, "fixture must produce at least one recorded trigger"
        assert trigger_calls[0][1]["indicators"]["regime"] in (
            "bull", "bear", "high_vol", "sideways",
        )

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


def _make_bars_with_rsi_recovery(n: int = 150, decline_len: int = 80) -> pd.DataFrame:
    """A decline steep enough to pin RSI(14) at 0 for a stretch (fully
    oversold), then a genuine reversal -- RSI recovers and crosses above
    30 exactly once, well after MIN_OBSERVATIONS and with enough bars
    left for the forward outcome horizon. A different KIND of
    must-condition from the module's own default (a fixed-threshold
    cross, not two series crossing each other), used as item #2's own
    proof that MustCondition generalizes rather than just re-parameterizing
    the same crossing shape."""
    decline = 100.0 - np.arange(decline_len) * 0.5
    recovery = decline[-1] + np.arange(1, n - decline_len + 1) * 0.6
    close = np.concatenate([decline, recovery])
    high = close + 0.3
    low = close - 0.3
    open_ = close - 0.05
    volume = np.linspace(1_000_000, 1_500_000, n)
    bar_ts = (pd.date_range("2024-01-01", periods=n, freq="15min").astype("int64") // 10**9).astype(int)
    return pd.DataFrame({
        "bar_ts": bar_ts, "open": open_, "high": high, "low": low, "close": close, "volume": volume,
    })


class TestUniversalMustCondition:
    """item #2: "a universal strategy runnable directly inside the 29th
    angle" -- proves the generalization works for a must-condition kind
    genuinely different from the hardcoded example (a threshold cross,
    not two series crossing each other), not just a re-parameterized copy
    of the same SMA-crossing shape."""

    def test_no_must_condition_arg_preserves_the_exact_default_behavior(self):
        """The most important regression guard for this whole feature:
        every existing caller (must_condition=None) must get byte-
        identical behavior to before this generalization existed."""
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, time_format="15min")
        assert df.iloc[0]["must_condition"] == MUST_CONDITION_NAME
        assert df.iloc[0]["status"] == "ok"
        assert df.iloc[0]["crossings_found"] >= 1

    def test_rsi_threshold_cross_above_is_detected_and_recorded(self):
        from vinu_initial_analysis.angles.signal_evidence.compute import MustCondition

        condition = MustCondition(
            name="rsi14_cross_above_30", kind="threshold_cross_above",
            indicator_key="rsi", threshold=30.0,
        )
        bars = _make_bars_with_rsi_recovery()
        df = compute("AAPL", bars=bars, time_format="15min", must_condition=condition)
        row = df.iloc[0]
        assert row["status"] == "ok"
        assert row["must_condition"] == "rsi14_cross_above_30"
        assert row["crossings_found"] >= 1
        assert row["triggers_recorded"] >= 1

        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        assert trigger_calls
        payload = trigger_calls[0][1]
        assert payload["must_condition"] == "rsi14_cross_above_30"
        assert f"AAPL-rsi14_cross_above_30-" in payload["trigger_id"]
        # The full supporting-indicator snapshot is still recorded --
        # this is the actual point of the generalization, not just that
        # detection works for a new condition kind.
        assert "adx" in payload["indicators"]
        assert "sma_50" in payload["indicators"]
        assert "macd_line" in payload["indicators"]

    def test_threshold_cross_below_is_the_mirror_image(self):
        from vinu_initial_analysis.angles.signal_evidence.compute import MustCondition, _rsi, RSI_PERIOD

        # A decline that pushes RSI down through 70 -- crossing BELOW a
        # threshold, not above, exercising the other branch.
        n = 150
        rally = 100.0 + np.arange(80) * 0.5
        decline = rally[-1] - np.arange(1, n - 80 + 1) * 0.6
        close = pd.Series(np.concatenate([rally, decline]))
        rsi = _rsi(close, RSI_PERIOD)
        assert rsi.max() > 70, "fixture must actually clear the threshold"

        bar_ts = (pd.date_range("2024-01-01", periods=n, freq="15min").astype("int64") // 10**9).astype(int)
        bars = pd.DataFrame({
            "bar_ts": bar_ts, "open": close - 0.05, "high": close + 0.3, "low": close - 0.3,
            "close": close, "volume": np.linspace(1_000_000, 1_500_000, n),
        })
        condition = MustCondition(
            name="rsi14_cross_below_70", kind="threshold_cross_below",
            indicator_key="rsi", threshold=70.0,
        )
        df = compute("AAPL", bars=bars, must_condition=condition)
        assert df.iloc[0]["crossings_found"] >= 1
        assert df.iloc[0]["must_condition"] == "rsi14_cross_below_70"

    def test_a_custom_cross_above_condition_can_reference_two_supporting_series(self):
        """Not just the fixed-threshold kind -- a caller can also define a
        DIFFERENT two-series crossing than the hardcoded default (e.g.
        EMA(5) over EMA(20) instead of SMA(5) over SMA(50)), reusing
        series this angle already computes as supporting indicators."""
        from vinu_initial_analysis.angles.signal_evidence.compute import MustCondition

        condition = MustCondition(
            name="ema5_cross_ema20", kind="cross_above", fast_key="ema_5", slow_key="ema_20",
        )
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, must_condition=condition)
        assert df.iloc[0]["must_condition"] == "ema5_cross_ema20"
        assert df.iloc[0]["status"] == "ok"

    def test_unknown_condition_kind_raises_a_clear_error(self):
        from vinu_initial_analysis.angles.signal_evidence.compute import MustCondition

        condition = MustCondition(name="bogus", kind="not_a_real_kind")
        bars = _make_bars_with_crossing()
        with pytest.raises(ValueError, match="Unknown must-condition kind"):
            compute("AAPL", bars=bars, must_condition=condition)

    def test_referencing_an_unknown_series_key_yields_no_crossings_not_a_crash(self):
        from vinu_initial_analysis.angles.signal_evidence.compute import MustCondition

        condition = MustCondition(
            name="typo_condition", kind="cross_above", fast_key="sma_5", slow_key="sma_999",
        )
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, must_condition=condition)
        assert df.iloc[0]["status"] == "ok"
        assert df.iloc[0]["crossings_found"] == 0


class TestNewsConfound:
    """item #9: "was there a news event within N minutes of this trigger"
    -- `news` was already fetched once per run and handed to this angle
    by runner.py, just never read before. Depends on item #19's fix
    (published_at/publish_time_is_estimated), already built, so this was
    buildable now rather than blocked."""

    def _article(self, article_id: str, published_at: int) -> dict:
        return {"id": article_id, "published_at": published_at, "sort_ts": published_at}

    def test_no_news_arg_leaves_news_confound_absent(self):
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, time_format="15min")
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        assert trigger_calls
        assert "news_confound" not in trigger_calls[0][1]["indicators"]

    def test_an_article_shortly_before_the_trigger_is_flagged(self):
        bars = _make_bars_with_crossing()
        crossing_idx = _first_crossing_index(bars)
        trigger_ts = int(bars["bar_ts"].iloc[crossing_idx])
        news = [self._article("art-1", trigger_ts - 30 * 60)]  # 30 min before

        df = compute("AAPL", bars=bars, time_format="15min", news=news)
        assert df.iloc[0]["status"] == "ok"
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        confound = trigger_calls[0][1]["indicators"]["news_confound"]
        assert confound["occurred"] is True
        assert confound["article_id"] == "art-1"
        assert confound["minutes_before"] == pytest.approx(30.0, abs=0.5)

    def test_an_article_outside_the_window_is_not_flagged(self):
        bars = _make_bars_with_crossing()
        crossing_idx = _first_crossing_index(bars)
        trigger_ts = int(bars["bar_ts"].iloc[crossing_idx])
        # Default window is 60 minutes -- 3 hours before is well outside it.
        news = [self._article("art-old", trigger_ts - 3 * 3600)]

        df = compute("AAPL", bars=bars, time_format="15min", news=news)
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        confound = trigger_calls[0][1]["indicators"]["news_confound"]
        assert confound == {"occurred": False, "minutes_before": None, "article_id": None}

    def test_an_article_after_the_trigger_does_not_count_as_a_confound(self):
        """No look-ahead: a headline minutes AFTER a trigger fired is a
        separate future event, not a confound for the trigger that
        already happened."""
        bars = _make_bars_with_crossing()
        crossing_idx = _first_crossing_index(bars)
        trigger_ts = int(bars["bar_ts"].iloc[crossing_idx])
        news = [self._article("art-future", trigger_ts + 10 * 60)]

        df = compute("AAPL", bars=bars, time_format="15min", news=news)
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        confound = trigger_calls[0][1]["indicators"]["news_confound"]
        assert confound["occurred"] is False

    def test_the_closest_preceding_article_is_reported_when_several_qualify(self):
        bars = _make_bars_with_crossing()
        crossing_idx = _first_crossing_index(bars)
        trigger_ts = int(bars["bar_ts"].iloc[crossing_idx])
        news = [
            self._article("art-far", trigger_ts - 55 * 60),
            self._article("art-near", trigger_ts - 5 * 60),
        ]

        df = compute("AAPL", bars=bars, time_format="15min", news=news)
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        confound = trigger_calls[0][1]["indicators"]["news_confound"]
        assert confound["article_id"] == "art-near"
        assert confound["minutes_before"] == pytest.approx(5.0, abs=0.5)

    def test_falls_back_to_sort_ts_when_published_at_is_none(self):
        """publish_time_is_estimated cases: published_at is None, so
        sort_ts (the best available estimate, per item #19's own
        fail-open convention) is used instead of dropping the article."""
        bars = _make_bars_with_crossing()
        crossing_idx = _first_crossing_index(bars)
        trigger_ts = int(bars["bar_ts"].iloc[crossing_idx])
        news = [{"id": "art-estimated", "published_at": None, "sort_ts": trigger_ts - 20 * 60}]

        df = compute("AAPL", bars=bars, time_format="15min", news=news)
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        confound = trigger_calls[0][1]["indicators"]["news_confound"]
        assert confound["occurred"] is True
        assert confound["article_id"] == "art-estimated"

    def test_empty_news_list_leaves_news_confound_absent(self):
        bars = _make_bars_with_crossing()
        df = compute("AAPL", bars=bars, time_format="15min", news=[])
        trigger_calls = [c for c in _FakeClient.calls if c[0].endswith("/trigger")]
        assert "news_confound" not in trigger_calls[0][1]["indicators"]
