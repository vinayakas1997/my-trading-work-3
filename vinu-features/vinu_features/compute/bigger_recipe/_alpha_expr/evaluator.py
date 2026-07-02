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


def _ref(arr: np.ndarray, k: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    if k >= 0:
        if k < len(arr):
            out[k:] = arr[: len(arr) - k]
    else:
        j = -k
        if j < len(arr):
            out[: len(arr) - j] = arr[j:]
    return out


def _rolling_mean(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.mean(x))


def _rolling_std(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.std(x, ddof=0))


def _rolling_sum(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.sum(x))


def _rolling_max(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.max(x))


def _rolling_min(arr: np.ndarray, w: int) -> np.ndarray:
    return _rolling_apply(arr, w, lambda x: np.min(x))


def _rolling_apply(arr: np.ndarray, w: int, fn) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    for i in range(w - 1, len(arr)):
        window = arr[i - w + 1 : i + 1]
        if np.any(np.isnan(window)):
            continue
        out[i] = fn(window)
    return out


def _rank(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    for i in range(w - 1, len(arr)):
        window = arr[i - w + 1 : i + 1]
        if np.isnan(window[-1]):
            continue
        out[i] = np.sum(window <= window[-1]) / w
    return out


def _quantile(arr: np.ndarray, w: int, q: float) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    for i in range(w - 1, len(arr)):
        window = arr[i - w + 1 : i + 1]
        out[i] = float(np.quantile(window, q))
    return out


def _slope(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    x = np.arange(w, dtype=float)
    for i in range(w - 1, len(arr)):
        y = arr[i - w + 1 : i + 1]
        if np.any(np.isnan(y)):
            continue
        xm, ym = x.mean(), y.mean()
        num = np.sum((x - xm) * (y - ym))
        den = np.sum((x - xm) ** 2)
        out[i] = num / den if den else 0.0
    return out


def _rsquare(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    x = np.arange(w, dtype=float)
    for i in range(w - 1, len(arr)):
        y = arr[i - w + 1 : i + 1]
        if np.any(np.isnan(y)):
            continue
        corr = np.corrcoef(x, y)[0, 1]
        out[i] = corr ** 2 if not np.isnan(corr) else 0.0
    return out


def _resi(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    x = np.arange(w, dtype=float)
    for i in range(w - 1, len(arr)):
        y = arr[i - w + 1 : i + 1]
        if np.any(np.isnan(y)):
            continue
        slope = _slope(arr, w)[i]
        intercept = y.mean() - slope * x.mean()
        pred = slope * x[-1] + intercept
        out[i] = y[-1] - pred
    return out


def _idxmax(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    for i in range(w - 1, len(arr)):
        window = arr[i - w + 1 : i + 1]
        out[i] = w - 1 - int(np.argmax(window))
    return out


def _idxmin(arr: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(arr, np.nan, dtype=float)
    for i in range(w - 1, len(arr)):
        window = arr[i - w + 1 : i + 1]
        out[i] = w - 1 - int(np.argmin(window))
    return out


def _corr(a: np.ndarray, b: np.ndarray, w: int) -> np.ndarray:
    out = np.full_like(a, np.nan, dtype=float)
    for i in range(w - 1, len(a)):
        xa = a[i - w + 1 : i + 1]
        xb = b[i - w + 1 : i + 1]
        if np.any(np.isnan(xa)) or np.any(np.isnan(xb)):
            continue
        c = np.corrcoef(xa, xb)[0, 1]
        out[i] = c if not np.isnan(c) else 0.0
    return out
