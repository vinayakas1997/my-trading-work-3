from __future__ import annotations

import contextlib
import io
import logging
from typing import Any

import numpy as np
import pandas as pd
from statsmodels.tsa.stattools import grangercausalitytests

LOG = logging.getLogger(__name__)


def run_granger_causality_test(
    news_series: pd.Series,
    return_series: pd.Series,
    max_lag: int = 12,
) -> dict[str, Any]:
    df = pd.DataFrame({"news": news_series, "returns": return_series})
    df = df.dropna()
    if len(df) < max_lag + 5:
        return {
            "granger_causes_prices": False,
            "best_lag_hours": 0,
            "best_lag_minutes": 0,
            "p_value": 1.0,
            "test_results": {},
        }

    best_lag = 1
    best_p = 1.0
    test_results = {}

    try:
        # No `verbose=` argument: statsmodels 0.15 removed it, and passing it raised a TypeError that the handler
        # below turned into "no causality" for every ticker. Older versions print; swallow that output instead.
        with contextlib.redirect_stdout(io.StringIO()):
            gct = grangercausalitytests(df[["returns", "news"]], max_lag)
        for lag, result in gct.items():
            p = result[0]["ssr_ftest"][1]
            test_results[int(lag)] = {
                "ssr_ftest_p": float(p),
            }
            if p < best_p:
                best_p = p
                best_lag = lag
    except Exception as exc:
        # Still fail open (no causal claim), but never silently: a failure here is not evidence of "no causality".
        LOG.exception("granger test failed; reporting no causal claim")
        return {
            "granger_causes_prices": False,
            "best_lag_hours": 0,
            "best_lag_minutes": 0,
            "p_value": 1.0,
            "test_results": {},
            "error": f"{type(exc).__name__}: {exc}",
        }

    return {
        "granger_causes_prices": bool(best_p < 0.05),
        "best_lag_hours": best_lag,
        "best_lag_minutes": best_lag * 60,
        "p_value": float(best_p),
        "test_results": test_results,
    }
