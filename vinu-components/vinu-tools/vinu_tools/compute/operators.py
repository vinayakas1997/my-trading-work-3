from __future__ import annotations

import numpy as np


def rank(df: np.ndarray, axis: int = 1) -> np.ndarray:
    """Cross-sectional percentile rank per row (0-1 range)."""
    if df.ndim == 1:
        df = df.reshape(-1, 1)
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(df.shape[0]):
        row = df[i, :]
        valid = ~np.isnan(row)
        if valid.sum() > 1:
            ranks = np.argsort(np.argsort(row[valid]))
            result[i, valid] = ranks / (len(ranks) - 1) if len(ranks) > 1 else 0.5
        elif valid.sum() == 1:
            result[i, valid] = 0.5
    return result


def cs_rank(df: np.ndarray) -> np.ndarray:
    """Cross-sectional rank (alias for rank)."""
    return rank(df)


def zscore(df: np.ndarray, axis: int = 1) -> np.ndarray:
    """Cross-sectional z-score per row."""
    if df.ndim == 1:
        df = df.reshape(-1, 1)
    result = np.zeros_like(df, dtype=float)
    for i in range(df.shape[0]):
        row = df[i, :]
        valid = ~np.isnan(row)
        if valid.sum() > 1:
            mean = np.nanmean(row)
            std = np.nanstd(row)
            if std > 0:
                result[i, valid] = (row[valid] - mean) / std
    return result


def scale(df: np.ndarray) -> np.ndarray:
    """Scale to [-1, 1] range per row."""
    if df.ndim == 1:
        df = df.reshape(-1, 1)
    result = np.zeros_like(df, dtype=float)
    for i in range(df.shape[0]):
        row = df[i, :]
        valid = ~np.isnan(row)
        if valid.sum() > 0:
            rmin, rmax = np.nanmin(row), np.nanmax(row)
            if rmax > rmin:
                result[i, valid] = 2 * (row[valid] - rmin) / (rmax - rmin) - 1
    return result


def ts_rank(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling rank over n-period window."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        for j in range(df.shape[1]):
            col = window[:, j]
            valid = ~np.isnan(col)
            if valid.sum() > 1:
                last = col[-1]
                r = np.sum(col[valid] < last) / valid.sum()
                result[i, j] = r
    return result


def ts_corr(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """Rolling Pearson correlation between x and y over n-period window."""
    assert x.shape == y.shape, "x and y must have same shape"
    result = np.full_like(x, np.nan, dtype=float)
    for i in range(n - 1, x.shape[0]):
        wx = x[max(0, i - n + 1):i + 1, :]
        wy = y[max(0, i - n + 1):i + 1, :]
        for j in range(x.shape[1]):
            cx = wx[:, j]
            cy = wy[:, j]
            valid = ~(np.isnan(cx) | np.isnan(cy))
            if valid.sum() > 2:
                corr = np.corrcoef(cx[valid], cy[valid])[0, 1]
                result[i, j] = corr if not np.isnan(corr) else 0.0
    return result


def ts_cov(x: np.ndarray, y: np.ndarray, n: int) -> np.ndarray:
    """Rolling covariance between x and y over n-period window."""
    assert x.shape == y.shape
    result = np.full_like(x, np.nan, dtype=float)
    for i in range(n - 1, x.shape[0]):
        wx = x[max(0, i - n + 1):i + 1, :]
        wy = y[max(0, i - n + 1):i + 1, :]
        for j in range(x.shape[1]):
            cx = wx[:, j]
            cy = wy[:, j]
            valid = ~(np.isnan(cx) | np.isnan(cy))
            if valid.sum() > 2:
                cov = np.cov(cx[valid], cy[valid])[0, 1]
                result[i, j] = cov if not np.isnan(cov) else 0.0
    return result


def ts_mean(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling mean over n-period window."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        result[i, :] = np.nanmean(window, axis=0)
    return result


def ts_std(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling standard deviation over n-period window."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        result[i, :] = np.nanstd(window, axis=0)
    return result


def ts_max(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling max over n-period window."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        result[i, :] = np.nanmax(window, axis=0)
    return result


def ts_min(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling min over n-period window."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        result[i, :] = np.nanmin(window, axis=0)
    return result


def ts_argmax(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling argmax over n-period window (returns position 0..n-1)."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        for j in range(df.shape[1]):
            col = window[:, j]
            valid = ~np.isnan(col)
            if valid.sum() > 0:
                result[i, j] = float(np.nanargmax(col))
    return result


def ts_argmin(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling argmin over n-period window (returns position 0..n-1)."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        for j in range(df.shape[1]):
            col = window[:, j]
            valid = ~np.isnan(col)
            if valid.sum() > 0:
                result[i, j] = float(np.nanargmin(col))
    return result


def delta(df: np.ndarray, d: int = 1) -> np.ndarray:
    """Difference at lag d (d >= 1 to prevent lookahead)."""
    assert d >= 1, "d must be >= 1 to prevent lookahead"
    result = np.full_like(df, np.nan, dtype=float)
    if d < df.shape[0]:
        result[d:, :] = df[d:, :] - df[:-d, :]
    return result


def decay_linear(df: np.ndarray, n: int) -> np.ndarray:
    """Linear decay-weighted moving average."""
    result = np.full_like(df, np.nan, dtype=float)
    weights = np.arange(1, n + 1, dtype=float)
    weights /= weights.sum()
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        for j in range(df.shape[1]):
            col = window[:, j]
            valid = ~np.isnan(col)
            if valid.sum() > 0:
                w = weights[-valid.sum():]
                result[i, j] = np.dot(col[valid], w)
    return result


def signed_power(df: np.ndarray, e: float = 2.0) -> np.ndarray:
    """Signed power transformation: sign(x) * |x|^e."""
    return np.sign(df) * np.abs(df) ** e


def safe_div(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """Safe division: x / y, returns 0 where y == 0 or either is NaN."""
    result = np.zeros_like(x, dtype=float)
    valid = ~(np.isnan(x) | np.isnan(y) | (y == 0))
    result[valid] = x[valid] / y[valid]
    return result


def vwap(close: np.ndarray, volume: np.ndarray) -> np.ndarray:
    """Volume-weighted average price."""
    return safe_div(np.cumsum(close * volume, axis=0), np.cumsum(volume, axis=0))


def ts_sum(df: np.ndarray, n: int) -> np.ndarray:
    """Rolling sum over n-period window."""
    result = np.full_like(df, np.nan, dtype=float)
    for i in range(n - 1, df.shape[0]):
        window = df[max(0, i - n + 1):i + 1, :]
        result[i, :] = np.nansum(window, axis=0)
    return result


# ── DataFrame wrappers (moved from _compat.py) ────────────────

import pandas as pd


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


# Public DataFrame-aware wrappers (same names as numpy versions)
rank_df = _wrap1(rank)
zscore_df = _wrap1(zscore)
scale_df = _wrap1(scale)
ts_rank_df = _wrap1(ts_rank)
ts_mean_df = _wrap1(ts_mean)
ts_std_df = _wrap1(ts_std)
ts_max_df = _wrap1(ts_max)
ts_min_df = _wrap1(ts_min)
ts_argmax_df = _wrap1(ts_argmax)
ts_argmin_df = _wrap1(ts_argmin)
ts_sum_df = _wrap1(ts_sum)
decay_linear_df = _wrap1(decay_linear)
ts_corr_df = _wrap2(ts_corr)
ts_cov_df = _wrap2(ts_cov)
safe_div_df = _wrap2(safe_div)
delta_df = _wrap1(delta)
vwap_df = _wrap_vwap(vwap)
