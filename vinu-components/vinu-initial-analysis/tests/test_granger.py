import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.news_price_causality.granger import run_granger_causality_test as _run_granger_test


def test_granger_detects_causality():
    np.random.seed(42)
    n = 200
    news = np.zeros(n)
    returns = np.zeros(n)

    news[10] = 1
    for i in range(11, n):
        news[i] = 0.5 * news[i-1] + np.random.normal(0, 0.1)
        returns[i] = 0.3 * news[i-1] + np.random.normal(0, 0.1)

    result = _run_granger_test(pd.Series(news), pd.Series(returns), max_lag=5)
    assert result["p_value"] < 0.05
    assert result["granger_causes_prices"] is True


def test_granger_no_causality():
    np.random.seed(42)
    n = 200
    independent = pd.Series(np.random.normal(0, 1, n))
    dependent = pd.Series(np.random.normal(0, 1, n))

    result = _run_granger_test(independent, dependent, max_lag=5)
    assert result["p_value"] > 0.05 or result["granger_causes_prices"] is False


def test_granger_insufficient_data():
    result = _run_granger_test(pd.Series([1, 2, 3]), pd.Series([4, 5, 6]), max_lag=5)
    assert result["p_value"] == 1.0


def test_a_failing_statsmodels_call_is_reported_not_passed_off_as_no_causality(monkeypatch):
    """statsmodels 0.15 removed `verbose=`; the call raised a TypeError that was swallowed into p=1.0, so the angle
    reported 'no causality' for every ticker. A failure must carry its error."""
    import vinu_initial_analysis.angles.news_price_causality.granger as g

    def boom(*_a, **_k):
        raise TypeError("unexpected keyword argument")

    monkeypatch.setattr(g, "grangercausalitytests", boom)
    rng = np.random.default_rng(0)
    result = g.run_granger_causality_test(pd.Series(rng.normal(size=100)), pd.Series(rng.normal(size=100)), max_lag=3)
    assert result["granger_causes_prices"] is False
    assert "TypeError" in result["error"]


def test_few_observations_cap_the_lag_instead_of_failing():
    """30 observations with the default 12 lags used to raise 'Insufficient observations. Maximum allowable lag is 8'
    inside statsmodels and be logged as an ERROR traceback every time the angle ran."""
    rng = np.random.default_rng(1)
    idx = pd.RangeIndex(30)
    out = _run_granger_test(pd.Series(rng.normal(size=30), index=idx), pd.Series(rng.normal(size=30), index=idx))
    assert "error" not in out
    assert out["test_results"] and max(out["test_results"]) <= 8


def test_too_few_observations_to_test_at_all_is_insufficient_not_an_error():
    idx = pd.RangeIndex(6)
    out = _run_granger_test(pd.Series(range(6), index=idx, dtype=float), pd.Series(range(6), index=idx, dtype=float))
    assert out["p_value"] == 1.0 and out["test_results"] == {} and "error" not in out
