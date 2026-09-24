"""Signal Evidence -- angle #29, the historical-backfill half of
missing-pieces-of-system/new-theory-of-trading (Decision 10 of
01-planning.md: run the must-condition trigger detector as an angle in
this same pipeline, not a separate live-only watcher).

Walks a symbol's OWN bars (already fetched for whatever [from_ts, to_ts]
window this run was asked to cover -- the exact same screener -> download
-> run-angles pipeline every other angle already goes through) looking
for every historical firing of the must-condition (SMA(5) crosses above
SMA(50), the running example from the design doc), and for each one:

1. Computes a small set of SUPPORTING INDICATORS strictly point-in-time
   from bars up to and including the trigger bar -- ADX(14), RSI(14),
   volume-vs-20-bar-average. Deliberately NOT pulled from other angles'
   already-stored "latest" results: those reflect whenever that angle
   last happened to run, not the historical trigger moment, so using
   them here would silently leak look-ahead bias into the evidence table
   for any trigger that isn't from today. Real angle outputs (the 28
   angles) remain valid supporting-indicator columns for LIVE triggers
   (where "latest" genuinely means "now"), just not for this backfill
   path -- see 02-implementation-status.md's own limitations note.
2. Computes the OUTCOME PATH forward from the trigger bar (max favorable/
   adverse excursion, return at a fixed forward horizon) -- valid here
   specifically because backtesting already has the "future" bars
   sitting in the same DataFrame; this is not available at all for a
   live, still-open trigger, which is exactly why Phase 2's storage
   schema (Decision 1) allows the outcome fields to stay NULL until
   filled in later.
3. POSTs both to vinu-research's SignalEvidenceStore over HTTP (the same
   Decision 8 pattern feedback_loop.py's calibration push already uses),
   idempotently -- a trigger_id already recorded (a re-run over an
   overlapping window) is treated as success, not an error.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import numpy as np
import pandas as pd

from vinu_infra.model_policy import policy_version
from vinu_initial_analysis.config import get_angle_setting

ANGLE_NAME = "signal_evidence"
MUST_CONDITION_NAME = "sma5_cross_sma50"

# Needs enough lookback for SMA(50) + ADX(14)'s own smoothing warm-up
# before the first bar can produce a real (non-NaN) indicator reading.
MIN_OBSERVATIONS = get_angle_setting(ANGLE_NAME, "min_observations", 70)
SMA_FAST = get_angle_setting(ANGLE_NAME, "sma_fast", 5)
SMA_SLOW = get_angle_setting(ANGLE_NAME, "sma_slow", 50)
ADX_PERIOD = get_angle_setting(ANGLE_NAME, "adx_period", 14)
RSI_PERIOD = get_angle_setting(ANGLE_NAME, "rsi_period", 14)
VOLUME_AVG_PERIOD = get_angle_setting(ANGLE_NAME, "volume_avg_period", 20)
# Decision 2: 15-minute bars is the settled default recording granularity
# for swing-style must-conditions -- this angle's own outcome-horizon
# length (in BARS, not minutes) is a separate, explicitly-named knob,
# since "how many candles forward to measure the outcome over" and "what
# granularity a candle is" are two different decisions.
FORWARD_HORIZON_BARS = get_angle_setting(ANGLE_NAME, "forward_horizon_bars", 20)

RESEARCH_API_URL = os.getenv("VINU_RESEARCH_API_URL", "http://localhost:8087")
_HTTP_TIMEOUT_SEC = 5.0


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _rsi(close: pd.Series, period: int) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.where(avg_loss != 0.0, 100.0)


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Standard Wilder ADX, computed directly (no external TA package --
    this angle stays on the same numpy/pandas-only footing as the other
    classical-statistical angles, deliberately not model-category)."""
    up_move = high.diff()
    down_move = -low.diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()], axis=1
    ).max(axis=1)

    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    plus_di = 100.0 * pd.Series(plus_dm, index=high.index).ewm(
        alpha=1.0 / period, min_periods=period, adjust=False
    ).mean() / atr.replace(0.0, np.nan)
    minus_di = 100.0 * pd.Series(minus_dm, index=high.index).ewm(
        alpha=1.0 / period, min_periods=period, adjust=False
    ).mean() / atr.replace(0.0, np.nan)

    dx = 100.0 * (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0.0, np.nan)
    return dx.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()


def _find_crossings(fast: pd.Series, slow: pd.Series) -> list[int]:
    """Integer positions where `fast` crosses from <= `slow` to > `slow`,
    skipping any position where either side is still NaN (not enough
    lookback yet)."""
    above = fast > slow
    prev_above = above.shift(1)
    valid = fast.notna() & slow.notna() & prev_above.notna()
    prev_above_bool = prev_above.fillna(False).astype(bool)
    crossed = valid & above & ~prev_above_bool
    return list(np.flatnonzero(crossed.to_numpy()))


def _post_json(client: Any, url: str, payload: dict[str, Any]) -> tuple[bool, str]:
    try:
        resp = client.post(url, json=payload, timeout=_HTTP_TIMEOUT_SEC)
        if resp.status_code == 200:
            return True, "recorded"
        if resp.status_code == 409:
            return True, "already_recorded"
        return False, f"http_{resp.status_code}"
    except Exception as exc:  # noqa: BLE001 -- a network hiccup must not crash the whole angle run
        return False, f"error: {exc!r}"


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
            "symbol": symbol, "analysis_at": analysis_at, "angle": ANGLE_NAME, "status": "no_data",
        }])

    if len(bars) < MIN_OBSERVATIONS:
        return pd.DataFrame([{
            "symbol": symbol, "analysis_at": analysis_at, "angle": ANGLE_NAME,
            "status": "insufficient_data", "n_observations": int(len(bars)),
        }])

    close = bars["close"].astype(float)
    high = bars["high"].astype(float) if "high" in bars.columns else close
    low = bars["low"].astype(float) if "low" in bars.columns else close
    volume = bars["volume"].astype(float) if "volume" in bars.columns else None

    sma_fast = _sma(close, SMA_FAST)
    sma_slow = _sma(close, SMA_SLOW)
    adx = _adx(high, low, close, ADX_PERIOD)
    rsi = _rsi(close, RSI_PERIOD)
    vol_avg = volume.rolling(VOLUME_AVG_PERIOD).mean() if volume is not None else None

    crossings = _find_crossings(sma_fast, sma_slow)

    recorded = 0
    already_recorded = 0
    skipped_incomplete_horizon = 0
    record_errors = 0

    import httpx

    with httpx.Client(base_url=RESEARCH_API_URL) as client:
        for i in crossings:
            if i + FORWARD_HORIZON_BARS >= len(bars):
                # Real, honest gap: this crossing's outcome can't be
                # measured yet within the given window -- not recorded as
                # a failure, just not ready. A later run whose `to_ts`
                # extends further forward will pick it up.
                skipped_incomplete_horizon += 1
                continue

            indicators: dict[str, Any] = {}
            if not pd.isna(adx.iloc[i]):
                indicators["adx"] = float(adx.iloc[i])
            if not pd.isna(rsi.iloc[i]):
                indicators["rsi"] = float(rsi.iloc[i])
            if vol_avg is not None and not pd.isna(vol_avg.iloc[i]) and vol_avg.iloc[i] > 0:
                indicators["volume_vs_avg20"] = float(volume.iloc[i] / vol_avg.iloc[i])

            entry_price = float(close.iloc[i])
            forward = close.iloc[i + 1: i + 1 + FORWARD_HORIZON_BARS]
            max_favorable_excursion = float((forward.max() - entry_price) / entry_price)
            max_adverse_excursion = float((forward.min() - entry_price) / entry_price)
            return_at_horizon = float((forward.iloc[-1] - entry_price) / entry_price)

            if "bar_ts" in bars.columns:
                trigger_ts_raw = int(bars["bar_ts"].iloc[i])
                trigger_time = datetime.fromtimestamp(trigger_ts_raw, tz=timezone.utc).isoformat()
                trigger_id_ts = trigger_ts_raw
            else:
                trigger_time = analysis_at
                trigger_id_ts = i
            trigger_id = f"{symbol}-{MUST_CONDITION_NAME}-{trigger_id_ts}"

            ok, _reason = _post_json(
                client, "/research/signal-evidence/trigger",
                {
                    "trigger_id": trigger_id,
                    "symbol": symbol,
                    "trigger_time": trigger_time,
                    "must_condition": MUST_CONDITION_NAME,
                    "indicators": indicators,
                    "granularity": time_format or "15min",
                    "policy_version": policy_version(),
                },
            )
            if not ok:
                record_errors += 1
                continue
            if _reason == "already_recorded":
                already_recorded += 1
                continue

            ok_outcome, _reason2 = _post_json(
                client, f"/research/signal-evidence/{trigger_id}/outcome",
                {
                    "max_favorable_excursion": max_favorable_excursion,
                    "max_adverse_excursion": max_adverse_excursion,
                    "return_at_horizon": return_at_horizon,
                },
            )
            if ok_outcome:
                recorded += 1
            else:
                record_errors += 1

    return pd.DataFrame([{
        "symbol": symbol,
        "analysis_at": analysis_at,
        "angle": ANGLE_NAME,
        "status": "ok",
        "must_condition": MUST_CONDITION_NAME,
        "crossings_found": len(crossings),
        "triggers_recorded": recorded,
        "triggers_already_recorded": already_recorded,
        "triggers_skipped_incomplete_horizon": skipped_incomplete_horizon,
        "triggers_record_errors": record_errors,
    }])
