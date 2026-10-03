"""Pins the live detector's window size and feature list to what the vinu-tools warmup-drift budgets
were measured against (vinu-tools/tests/test_bias_checks.py: LIVE_WINDOW / LIVE_BASE_FEATURES).

The live poller computes features on a short trailing window; recursive indicators (EMA, MACD, ...)
differ from backtest by an amount that depends on that window. If either value below changes, the
drift budgets in test_bias_checks.py were measured for a different window and must be re-measured on
purpose, not silently inherited. (the-inconsistencies-v2 plan, Phase 5 item 5.2.)
"""

from vinu_live.live_decision.detector import BASE_FEATURE_NAMES, min_warmup_bars

EXPECTED_WINDOW = 201

EXPECTED_FEATURES = [
    "adx_14", "rsi_14", "sma_5", "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
    "ema_5", "ema_10", "ema_20", "ema_50", "ema_100", "ema_200", "roc_5", "roc_10", "roc_20",
    "atr_14", "stoch_k_14", "stoch_d_14", "bb_upper_20", "bb_mid_20", "bb_lower_20", "macd",
    "macd_signal", "aroon_up", "aroon_down", "cci_20", "williams_r_14", "supertrend",
    "high_low_spread", "open_close_return", "momentum_10", "ichimoku_tenkan", "ichimoku_kijun",
    "ichimoku_senkou_a", "ichimoku_senkou_b", "parabolic_sar", "obv", "volume_ratio_20",
    "cmf_20", "mfi_14", "accumulation_distribution_line",
]


def test_live_window_is_the_one_the_drift_budgets_were_measured_at():
    assert min_warmup_bars() == EXPECTED_WINDOW


def test_live_feature_list_matches_the_one_the_drift_budgets_cover():
    assert list(BASE_FEATURE_NAMES) == EXPECTED_FEATURES
