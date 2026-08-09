"""MOIRAI — Salesforce's any-variate time-series foundation model.

See ../../../New-talk-/Final-implementation/01-present-considerations/13-moirai.md
(method 13 of the 32-method plan). Its distinguishing feature is an
"any-variate" attention mechanism that lets one model call accept a
variable number of input series jointly (e.g. many tickers at once).

**Backend: fallback_proxy — real pretrained weights were NOT used, for
two independent reasons:**
1. `uni2ts` (Salesforce's real MOIRAI package, confirmed to exist on
   PyPI) pulls in `torch==2.4.1` as a hard dependency, which would
   *downgrade* the already-installed `torch==2.13.0+cpu` shared by this
   whole Python environment (other angles/components rely on it) — plus a
   large `jax`/`pytorch-lightning`/`tensorboard` dependency tree. Forcing
   a shared-environment torch downgrade to try one angle is not a safe
   trade, so this was not installed.
2. Structurally, this angle's `compute()` is called once per single
   `symbol` (see runner.py's `_run_angle` — no multi-ticker batching is
   exposed at this interface), so MOIRAI's actual differentiator
   (any-variate joint multi-series attention) couldn't be exercised here
   even with the real weights loaded — it would degrade to a single-variate
   call, same as Chronos/TimesFM.

Given both, this uses a statistical proxy: fits a small per-ticker linear
autoregression (AR(3) via least squares) and reports the forecast as a
single-variate degenerate case of what would otherwise be an any-variate
call, with `any_variate_note` making the degradation explicit.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting

ANGLE_NAME = "moirai"
# Decided value, 04-enhancement-of-each-angle/16-moirai.md — raised from
# 20, same consistency move as every other raised-floor angle.
# Overridable via VINU_MOIRAI_MIN_OBSERVATIONS -- see
# ../../../New-talk-/06-implementation-of-each-angles/adding-a-new-angle.md
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", DEFAULT_MIN_OBSERVATIONS)
HORIZON = 5
AR_ORDER = 3
FALLBACK_REASON = (
    "uni2ts (real MOIRAI package) would downgrade the shared environment's "
    "torch 2.13.0+cpu to torch==2.4.1 plus pull in jax/lightning — too "
    "risky to install for one angle; additionally this angle's per-symbol "
    "compute() call can't exercise MOIRAI's any-variate multi-ticker "
    "mechanism anyway, so a single-series AR(3) statistical proxy is used "
    "instead, explicitly labeled as the any-variate-degenerate case."
)
ANY_VARIATE_NOTE = (
    "This call is single-ticker only (compute() receives one symbol's "
    "bars at a time) — MOIRAI's any-variate joint-multi-series mechanism "
    "is not exercised; this is the single-variate degenerate case."
)


def _fit_ar(closes: np.ndarray, order: int) -> np.ndarray:
    returns = np.diff(closes) / closes[:-1]
    n = len(returns)
    X = np.column_stack([returns[i:n - order + i] for i in range(order)])
    y = returns[order:]
    coeffs, *_ = np.linalg.lstsq(X, y, rcond=None)
    return coeffs


def _forecast_ar(closes: np.ndarray, coeffs: np.ndarray, horizon: int) -> dict[str, Any]:
    order = len(coeffs)
    returns = list(np.diff(closes) / closes[:-1])
    resid = returns[order:] - np.column_stack(
        [returns[i:len(returns) - order + i] for i in range(order)]
    ) @ coeffs
    resid_std = float(np.std(resid, ddof=1)) if len(resid) > 1 else 0.0

    history = returns[-order:]
    price = float(closes[-1])
    point = []
    for _ in range(horizon):
        next_ret = float(np.dot(coeffs, history[-order:]))
        price = price * (1 + next_ret)
        point.append(price)
        history.append(next_ret)

    steps = np.arange(1, horizon + 1)
    spread = resid_std * np.sqrt(steps) * float(closes[-1])
    point_arr = np.array(point)
    return {
        "point_forecast": point_arr.tolist(),
        "p10_forecast": (point_arr - 1.2816 * spread).tolist(),
        "p90_forecast": (point_arr + 1.2816 * spread).tolist(),
    }


def _fit_and_forecast(closes: np.ndarray) -> dict[str, Any]:
    """Fits a fresh AR(3) OLS model on `closes` and forecasts `HORIZON`
    steps ahead with an 80% band (p10/p90). Returns every result field
    except symbol/analysis_at/angle (callers attach those). Pure
    closed-form solve, no trained-model object to save — same reasoning
    as lag_llama's own `_fit_and_forecast`, no weights artifact for the
    walk-forward backtest to store.
    """
    coeffs = _fit_ar(closes, AR_ORDER)
    forecast = _forecast_ar(closes, coeffs, HORIZON)
    return {
        "status": "ok",
        "n_observations": int(len(closes)),
        "model_backend": "fallback_proxy",
        "fallback_reason": FALLBACK_REASON,
        "any_variate_note": ANY_VARIATE_NOTE,
        "forecast_horizon": HORIZON,
        "last_close": float(closes[-1]),
        **forecast,
    }


def compute(
    symbol: str,
    bars: pd.DataFrame | None = None,
    news: list[dict] | None = None,
    from_ts: int | None = None,
    to_ts: int | None = None,
    time_format: str | None = None,
) -> pd.DataFrame:
    analysis_at = datetime.now(timezone.utc).isoformat()

    if bars is None or bars.empty:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "no_data",
        }])

    closes = bars["close"].astype(float).values
    if len(closes) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol,
            "analysis_at": analysis_at,
            "angle": ANGLE_NAME,
            "status": "insufficient_data",
            "n_observations": int(len(closes)),
        }])

    fields = _fit_and_forecast(closes)

    result: dict[str, Any] = {
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        **fields,
    }
    return pd.DataFrame([result])
