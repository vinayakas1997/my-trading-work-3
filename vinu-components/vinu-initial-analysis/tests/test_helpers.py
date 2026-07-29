import numpy as np

from vinu_initial_analysis.angles._helpers import (
    _compute_returns_series,
    classify_significance,
    compute_abnormal_return,
)


def test_compute_abnormal_return_with_drop():
    np.random.seed(0)
    price = 100.0
    pre_candles = []
    for i in range(100):
        price *= (1 + np.random.normal(0, 0.001))
        pre_candles.append({"bar_ts": i * 60, "open": price, "high": price * 1.001,
                            "low": price * 0.999, "close": price})

    event_ts = 100 * 60
    event_candles = []
    for j in range(10):
        price *= 0.995
        event_candles.append({"bar_ts": event_ts + j * 60, "open": price,
                              "high": price * 1.001, "low": price * 0.999, "close": price})

    candles = pre_candles + event_candles
    result = compute_abnormal_return(candles, event_ts)
    assert result["abnormal_return"] < 0
    assert result["significant"] is True


def test_compute_abnormal_return_insufficient_data():
    result = compute_abnormal_return([], 1000)
    assert result["ar_p_value"] == 1.0
    assert result["significant"] is False


def test_classify_significance():
    assert classify_significance(0.001) == "highly_significant"
    assert classify_significance(0.02) == "significant"
    assert classify_significance(0.07) == "marginally_significant"
    assert classify_significance(0.15) == "insignificant"


def test_compute_returns_series():
    candles = [
        {"bar_ts": 100, "close": 100.0},
        {"bar_ts": 200, "close": 110.0},
        {"bar_ts": 300, "close": 99.0},
    ]
    returns = _compute_returns_series(candles)
    assert len(returns) == 2
    assert returns[0] == 0.1
    assert abs(returns[1] - (-0.1)) < 0.001
