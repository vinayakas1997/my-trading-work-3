"""Qlib-style expression evaluation on OHLCV rows."""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

_REF_RE = re.compile(r"Ref\(\$([a-z]+),\s*(-?\d+)\)")
_FIELD_RE = re.compile(r"\$([a-z]+)")


def rows_to_arrays(rows: list[dict]) -> dict[str, np.ndarray]:
    close = np.array([float(r["close"]) for r in rows], dtype=float)
    open_ = np.array([float(r["open"]) for r in rows], dtype=float)
    high = np.array([float(r["high"]) for r in rows], dtype=float)
    low = np.array([float(r["low"]) for r in rows], dtype=float)
    volume = np.array([float(r.get("volume") or 0) for r in rows], dtype=float)
    vwap = (high + low + close) / 3.0
    return {"close": close, "open": open_, "high": high, "low": low, "volume": volume, "vwap": vwap}


def evaluate(expr: str, arrays: dict[str, np.ndarray]) -> list[float | None]:
    env = _build_env(arrays)
    py_expr = _to_python(expr)
    try:
        result = eval(py_expr, {"__builtins__": {}}, env)  # noqa: S307
    except Exception:
        return [None] * len(arrays["close"])
    if isinstance(result, (int, float)):
        return [float(result)] * len(arrays["close"])
    out: list[float | None] = []
    for v in np.asarray(result, dtype=float):
        if np.isnan(v) or np.isinf(v):
            out.append(None)
        else:
            out.append(float(v))
    return out


def _to_python(expr: str) -> str:
    s = expr
    s = _REF_RE.sub(r"ref(\1, \2)", s)
    s = _FIELD_RE.sub(r"\1", s)
    s = s.replace("&&", " and ").replace("||", " or ")
    return s


def _build_env(arrays: dict[str, np.ndarray]) -> dict[str, Any]:
    n = len(arrays["close"])
    env = dict(arrays)
    env.update(
        {
            "ref": lambda field, k: _ref(arrays[field], int(k)),
            "Mean": _rolling_mean,
            "Std": _rolling_std,
            "Sum": _rolling_sum,
            "Max": _rolling_max,
            "Min": _rolling_min,
            "Abs": np.abs,
            "Log": lambda x: np.log(np.maximum(x, 1e-12)),
            "Greater": np.maximum,
            "Less": np.minimum,
            "Rank": _rank,
            "Quantile": _quantile,
            "Slope": _slope,
            "Rsquare": _rsquare,
            "Resi": _resi,
            "IdxMax": _idxmax,
            "IdxMin": _idxmin,
            "Corr": _corr,
        }
    )
    return env


def _nan_like(arr: np.ndarray) -> np.ndarray:
    return np.empty_like(arr, dtype=float)


def _ref(arr: np.ndarray, k: int) -> np.ndarray:
    out = _nan_like(arr)
    if k >= 0:
        if k >= len(arr):
            out[:] = np.nan
        else:
            out[:k] = np.nan
            out[k:] = arr[: len(arr) - k]
    else:
        j = -k
        if j >= len(arr):
            out[:] = np.nan
        else:
            out[: len(arr) - j] = arr[j:]
            out[len(arr) - j:] = np.nan
    return out


def _rolling_mean(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.mean(x))


def _rolling_std(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.std(x, ddof=1))


def _rolling_sum(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.sum(x))


def _rolling_max(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.max(x))


def _rolling_min(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.min(x))


def _sliding_windows(arr: np.ndarray, w: int) -> np.ndarray | None:
    n = len(arr)
    if n < w:
        return None
    return np.lib.stride_tricks.sliding_window_view(arr, w)


def _rolling_apply(arr: np.ndarray, w: int, fn) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    mask = ~np.any(np.isnan(windows), axis=1)
    if mask.any():
        out[w - 1:][mask] = np.array([fn(w) for w in windows[mask]])
    return out


def _rank(arr: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    last_vals = windows[:, -1]
    mask = ~np.isnan(last_vals)
    out[w - 1:][mask] = np.sum(windows[mask] <= last_vals[mask, None], axis=1) / w
    return out


def _quantile(arr: np.ndarray, w: int, q: float) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    out[w - 1:] = np.quantile(windows, q, axis=1)
    return out


def _slope(arr: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    x = np.arange(w, dtype=float)
    xm, xvar = x.mean(), ((x - x.mean()) ** 2).sum()
    mask = ~np.any(np.isnan(windows), axis=1)
    if mask.any():
        ym = windows[mask].mean(axis=1)
        num = np.sum((windows[mask] - ym[:, None]) * (x - xm), axis=1)
        out[w - 1:][mask] = num / xvar
    return out


def _rsquare(arr: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    x = np.arange(w, dtype=float)
    mask = ~np.any(np.isnan(windows), axis=1)
    if mask.any():
        valid = windows[mask]
        corrs = np.array([np.corrcoef(x, y)[0, 1] for y in valid])
        out[w - 1:][mask] = np.where(np.isnan(corrs), 0.0, corrs ** 2)
    return out


def _resi(arr: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    x = np.arange(w, dtype=float)
    xm, xvar = x.mean(), ((x - x.mean()) ** 2).sum()
    mask = ~np.any(np.isnan(windows), axis=1)
    if mask.any():
        y = windows[mask]
        ym = y.mean(axis=1)
        slopes = np.sum((y - ym[:, None]) * (x - xm), axis=1) / xvar
        intercepts = ym - slopes * xm
        out[w - 1:][mask] = y[:, -1] - (slopes * x[-1] + intercepts)
    return out


def _idxmax(arr: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    out[w - 1:] = w - 1 - np.argmax(windows, axis=1).astype(float)
    return out


def _idxmin(arr: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(arr)
    out[:w - 1] = np.nan
    windows = _sliding_windows(arr, w)
    if windows is None:
        return out
    out[w - 1:] = w - 1 - np.argmin(windows, axis=1).astype(float)
    return out


def _corr(a: np.ndarray, b: np.ndarray, w: int) -> np.ndarray:
    out = _nan_like(a)
    out[:w - 1] = np.nan
    n = len(a)
    if n < w:
        return out
    a_wins = np.lib.stride_tricks.sliding_window_view(a, w)
    b_wins = np.lib.stride_tricks.sliding_window_view(b, w)
    mask = ~(np.any(np.isnan(a_wins), axis=1) | np.any(np.isnan(b_wins), axis=1))
    if mask.any():
        corrs = np.array([np.corrcoef(aw, bw)[0, 1] for aw, bw in zip(a_wins[mask], b_wins[mask])])
        out[w - 1:][mask] = np.where(np.isnan(corrs), 0.0, corrs)
    return out
