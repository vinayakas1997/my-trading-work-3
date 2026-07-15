"""Compatibility layer: wraps vinu-features numpy operators to accept DataFrames.

This allows Vibe-Trading factor files to run unmodified (only the import line changes).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_features.compute.operators import (
    cs_rank,
    decay_linear,
    delta,
    rank as _rank_np,
    safe_div as _safe_div_np,
    scale as _scale_np,
    signed_power,
    ts_argmax,
    ts_argmin,
    ts_corr as _ts_corr_np,
    ts_cov as _ts_cov_np,
    ts_max,
    ts_mean,
    ts_min,
    ts_rank as _ts_rank_np,
    ts_std,
    ts_sum,
    vwap as _vwap_np,
    zscore as _zscore_np,
)


def _wrap1(f):
    def wrapped(a, *args, **kwargs):
        if isinstance(a, pd.DataFrame):
            idx, cols = a.index, a.columns
            result = f(a.values, *args, **kwargs)
            return pd.DataFrame(result, index=idx, columns=cols)
        return f(a, *args, **kwargs)
    wrapped.__name__ = f.__name__
    wrapped.__qualname__ = f.__qualname__
    return wrapped


def _wrap2(f):
    def wrapped(a, b, *args, **kwargs):
        if isinstance(a, pd.DataFrame):
            idx, cols = a.index, a.columns
            b_arr = b.values if isinstance(b, pd.DataFrame) else b
            result = f(a.values, b_arr, *args, **kwargs)
            return pd.DataFrame(result, index=idx, columns=cols)
        return f(a, b, *args, **kwargs)
    wrapped.__name__ = f.__name__
    wrapped.__qualname__ = f.__qualname__
    return wrapped


def _wrap_vwap(f):
    def wrapped(panel_or_a, b=None, *args, **kwargs):
        if isinstance(panel_or_a, dict):
            panel = panel_or_a
            if "vwap" in panel:
                return panel["vwap"]
            if b and (isinstance(b, str) and "equity_cn" in b):
                if "amount" in panel and "volume" in panel:
                    amt = panel["amount"]
                    vol = panel["volume"]
                    return safe_div(amt * 1000.0, vol * 100.0 + 1.0)
            if all(k in panel for k in ("open", "high", "low", "close")):
                return (panel["open"] + panel["high"] + panel["low"] + panel["close"]) / 4.0
            return panel.get("close", pd.DataFrame())
        return f(panel_or_a, b, *args, **kwargs)
    return wrapped


def _wrap_zscore(f):
    def wrapped(a, *args, **kwargs):
        if isinstance(a, pd.DataFrame):
            idx, cols = a.index, a.columns
            result = f(a.values, *args, **kwargs)
            return pd.DataFrame(result, index=idx, columns=cols)
        return f(a, *args, **kwargs)
    return wrapped


rank = _wrap1(_rank_np)
zscore = _wrap1(_zscore_np)
scale = _wrap1(_scale_np)
ts_rank = _wrap1(_ts_rank_np)
ts_mean = _wrap1(ts_mean)
ts_std = _wrap1(ts_std)
ts_max = _wrap1(ts_max)
ts_min = _wrap1(ts_min)
ts_argmax = _wrap1(ts_argmax)
ts_argmin = _wrap1(ts_argmin)
ts_sum = _wrap1(ts_sum)
decay_linear = _wrap1(decay_linear)
ts_corr = _wrap2(_ts_corr_np)
ts_cov = _wrap2(_ts_cov_np)
safe_div = _wrap2(_safe_div_np)
delta = _wrap1(delta)
vwap = _wrap_vwap(_vwap_np)


__all__ = [
    "rank", "zscore", "scale", "ts_rank", "ts_corr", "ts_cov",
    "ts_mean", "ts_std", "ts_max", "ts_min", "ts_argmax", "ts_argmin",
    "delta", "decay_linear", "signed_power", "safe_div", "vwap", "ts_sum",
    "cs_rank",
]
