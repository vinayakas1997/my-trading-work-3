import numpy as np
import pandas as pd

from vinu_correlation.engine.granger import run_granger_causality_test as _run_granger_test


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
