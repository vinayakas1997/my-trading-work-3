from __future__ import annotations

from vinu_initial_analysis.storage.run_id import (
    ANGLE_SHORTCODES,
    TIME_FORMAT_CODES,
    angle_code,
    generate_run_id,
    time_format_code,
)


def test_format_shape_and_fields():
    run_id = generate_run_id("AAPL", "arima", "1D", 1640995200, 1656633600, 1)
    parts = run_id.split("_")
    assert parts[0] == "AAPL"
    assert parts[1] == "arima"
    assert parts[2] == "1d"
    assert parts[3] == "220101"  # 2022-01-01 UTC
    assert parts[4] == "220701"  # 2022-07-01 UTC
    assert parts[5] == "01"
    assert len(parts[6]) == 5  # random safety-net suffix


def test_every_real_angle_has_a_stable_code():
    """All 28 real angle ids from angles.yaml must be present -- a
    missing one would silently fall back to a truncated/sanitized id
    instead of the intended short code."""
    real_angle_ids = {
        "arima", "backtesting_44_metrics", "chronos", "dlinear",
        "drawdown_deep_dive", "exponential_smoothing", "garch",
        "itransformer", "kalman_filters", "kronos", "lag_llama",
        "lpatchtst", "lstm", "moirai", "moment", "news_price_causality",
        "patchtst", "peer_relative_strength", "pnl_attribution",
        "regime_analysis", "shock_clustering", "shock_personality",
        "tft", "timer_timerxl", "timesfm", "tips_regime_aware_transformer",
        "trend_lifecycle", "trend_session_structure",
    }
    assert real_angle_ids == set(ANGLE_SHORTCODES.keys())
    assert len(real_angle_ids) == 28


def test_angle_codes_are_unique():
    """Two angles sharing a code would make run_ids ambiguous -- the
    whole point of this scheme is decoding without a lookup table."""
    codes = list(ANGLE_SHORTCODES.values())
    assert len(codes) == len(set(codes))


def test_time_format_codes_are_unique_and_disambiguate_minute_vs_month():
    codes = list(TIME_FORMAT_CODES.values())
    assert len(codes) == len(set(codes))
    assert time_format_code("1min") != time_format_code("1M")


def test_unknown_angle_falls_back_without_raising():
    code = angle_code("some_brand_new_angle_not_yet_registered")
    assert code  # non-empty
    assert "_" not in code  # never contains the id separator


def test_unknown_time_format_falls_back_without_raising():
    code = time_format_code("weird_new_format")
    assert code
    assert "_" not in code


def test_ticker_with_literal_hyphen_does_not_break_field_count():
    """A real share-class ticker (e.g. BRK-B) must not shift later
    fields when the id is split on '_'."""
    run_id = generate_run_id("BRK-B", "arima", "1D", None, None, 1)
    parts = run_id.split("_")
    assert len(parts) == 7
    assert "-" not in parts[0]


def test_missing_dates_use_placeholder_not_none_or_crash():
    run_id = generate_run_id("AAPL", "arima", "1D", None, None, 1)
    parts = run_id.split("_")
    assert parts[3] == "000000"
    assert parts[4] == "000000"


def test_sequence_grows_past_two_digits_without_truncating():
    run_id = generate_run_id("AAPL", "arima", "1D", None, None, 123)
    parts = run_id.split("_")
    assert parts[5] == "123"


def test_two_calls_with_identical_inputs_still_differ_via_random_suffix():
    """This is the actual collision-safety property the design relies
    on for the concurrent tier3 trigger path: identical deterministic
    inputs must not produce identical ids."""
    a = generate_run_id("AAPL", "arima", "1D", 1640995200, 1656633600, 5)
    b = generate_run_id("AAPL", "arima", "1D", 1640995200, 1656633600, 5)
    assert a != b
    assert a.rsplit("_", 1)[0] == b.rsplit("_", 1)[0]  # deterministic part matches
