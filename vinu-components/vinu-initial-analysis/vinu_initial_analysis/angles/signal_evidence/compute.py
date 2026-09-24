"""Signal Evidence -- angle #29, the historical-backfill half of
missing-pieces-of-system/new-theory-of-trading (Decision 10 of
01-planning.md: run the must-condition trigger detector as an angle in
this same pipeline, not a separate live-only watcher).

Walks a symbol's OWN bars (already fetched for whatever [from_ts, to_ts]
window this run was asked to cover -- the exact same screener -> download
-> run-angles pipeline every other angle already goes through) looking
for every historical firing of the must-condition (SMA(5) crosses above
SMA(50), the running example from the design doc), and for each one:

1. Computes SUPPORTING INDICATORS strictly point-in-time from bars up to
   and including the trigger bar -- every indicator from
   all-possible-supporting-indicators.md Section H/I that's actually
   computable from bars alone: ADX, RSI, SMA/EMA (6 lengths each) plus
   their distance-from-price derivatives, ROC(5/10/20), ATR(14),
   Stochastic %K/%D, Bollinger band width/%B, MACD line/signal/
   histogram, Aroon up/down, CCI, Williams %R, Supertrend, high-low
   spread, open-close return, momentum, Ichimoku (Tenkan/Kijun/Senkou
   A/B), Parabolic SAR, OBV, volume-vs-20-bar-average, VWAP distance
   (session-sliced by UTC calendar date, see `_vwap_supporting`),
   Chaikin Money Flow, Money Flow Index, and the Accumulation/
   Distribution line -- every candidate from that doc's list is now
   wired in. All
   computed via vinu_tools' existing, tested indicator library, never
   hand-rolled -- see 06-mistake-duplicated-indicator-logic.md for why
   that matters (ADX/RSI used to be hand-rolled here, which was a
   mistake, now fixed; Ichimoku/Parabolic SAR/MFI/A-D line didn't exist
   in vinu_tools at all until this design needed them, so they were
   added there first as real reusable modules, not hand-rolled inline
   here -- the same anti-duplication reasoning applied forward instead
   of repeated). Each is a single
   vectorized pass over the whole bar history; per-trigger values are
   read out by position when a row is assembled to write, so indicator
   computation is column-wise but the evidence store write is row-wise
   (one full feature vector per trigger event, per Decision 1). Longer
   lookbacks (sma_200 etc.) simply come back absent for triggers early in
   a ticker's history that don't have enough bars yet -- not an error,
   just "not available yet," same as every other indicator here.
   Deliberately NOT pulled from other angles' already-stored
   "latest" results: those reflect whenever that angle last happened to
   run, not the historical trigger moment, so using them here would
   silently leak look-ahead bias into the evidence table for any trigger
   that isn't from today. Real angle outputs (the 28 angles) remain
   valid supporting-indicator columns for LIVE triggers (where "latest"
   genuinely means "now"), just not for this backfill path -- see
   02-implementation-status.md's own limitations note.
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
from vinu_tools.compute.indicators.accumulation_distribution_line.accumulation_distribution_line import (
    compute as _ad_line_compute,
)
from vinu_tools.compute.indicators.adx.adx import compute as _adx_compute
from vinu_tools.compute.indicators.aroon.aroon import compute as _aroon_compute
from vinu_tools.compute.indicators.atr.atr import compute as _atr_compute
from vinu_tools.compute.indicators.bollinger.bollinger import compute as _bollinger_compute
from vinu_tools.compute.indicators.cci.cci import compute as _cci_compute
from vinu_tools.compute.indicators.chaikin_money_flow.chaikin_money_flow import compute as _cmf_compute
from vinu_tools.compute.indicators.ema.ema import compute as _ema_compute
from vinu_tools.compute.indicators.high_low_spread.high_low_spread import compute as _high_low_spread_compute
from vinu_tools.compute.indicators.ichimoku.ichimoku import compute as _ichimoku_compute
from vinu_tools.compute.indicators.macd.macd import _macd as _macd_line_and_signal
from vinu_tools.compute.indicators.mfi.mfi import compute as _mfi_compute
from vinu_tools.compute.indicators.momentum_n.momentum_n import compute as _momentum_compute
from vinu_tools.compute.indicators.obv.obv import compute as _obv_compute
from vinu_tools.compute.indicators.open_close_return.open_close_return import compute as _open_close_return_compute
from vinu_tools.compute.indicators.parabolic_sar.parabolic_sar import compute as _parabolic_sar_compute
from vinu_tools.compute.indicators.roc.roc import compute as _roc_compute
from vinu_tools.compute.indicators.rsi.rsi import compute as _rsi_compute
from vinu_tools.compute.indicators.sma.sma import compute as _sma_tools_compute
from vinu_tools.compute.indicators.stochastic.stochastic import compute as _stochastic_compute
from vinu_tools.compute.indicators.supertrend.supertrend import compute as _supertrend_compute
from vinu_tools.compute.indicators.volume_ratio.volume_ratio import compute as _volume_ratio_compute
from vinu_tools.compute.indicators.vwap.vwap import compute as _vwap_compute
from vinu_tools.compute.indicators.williams_r.williams_r import compute as _williams_r_compute

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

# The exploded column list from all-possible-supporting-indicators.md
# Section H -- every length is its own column, not a shared family column
# (per that doc's own convention). Longer lengths (100, 200) will simply
# come back NaN/skipped for triggers early in a ticker's history that
# don't have enough bars yet -- same "record what's available" behavior
# already used for adx/rsi (Decision 1: nothing is forced).
SMA_LENGTHS = (5, 10, 20, 50, 100, 200)
EMA_LENGTHS = (5, 10, 20, 50, 100, 200)
ROC_LENGTHS = (5, 10, 20)
CCI_PERIOD = get_angle_setting(ANGLE_NAME, "cci_period", 20)
WILLIAMS_R_PERIOD = get_angle_setting(ANGLE_NAME, "williams_r_period", 14)
CMF_PERIOD = get_angle_setting(ANGLE_NAME, "cmf_period", 20)
MOMENTUM_PERIOD = get_angle_setting(ANGLE_NAME, "momentum_period", 10)
MFI_PERIOD = get_angle_setting(ANGLE_NAME, "mfi_period", 14)
# NOT get_angle_setting-configurable, unlike the periods above: these
# three feed a "one call returns every named column" optimization (see
# _stochastic_supporting/_bollinger_supporting/_aroon_supporting) that
# only works because vinu_tools' own compute() always falls back to
# ITS OWN hardcoded default params when called with a non-matching
# `name`. A configurable override here would silently be ignored by
# vinu_tools internally while this angle's key lookup still expected the
# overridden period -- a KeyError trap. Section H doesn't ask for
# multiple lengths of these anyway (unlike SMA/EMA/ROC), so there's
# nothing to configure.
STOCH_PERIOD = 14
STOCH_SMOOTH = 3
BOLLINGER_PERIOD = 20
AROON_PERIOD = 25


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(period).mean()


def _adx(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    """Thin wrapper around vinu_tools' real, tested ADX implementation
    (same bridging pattern drawdown_deep_dive/drawdown.py already uses
    for ATR: bars -> list[dict] rows in, named column back out) -- see
    06-mistake-duplicated-indicator-logic.md for why this used to be
    hand-rolled here and why that was a mistake."""
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    col_name = f"adx_{period}"
    result = _adx_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=high.index)


def _rsi(close: pd.Series, period: int) -> pd.Series:
    """Thin wrapper around vinu_tools' real, tested RSI implementation --
    see `_adx` above and 06-mistake-duplicated-indicator-logic.md."""
    rows = pd.DataFrame({"close": close}).to_dict("records")
    col_name = f"rsi_{period}"
    result = _rsi_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _sma_supporting(close: pd.Series, period: int) -> pd.Series:
    """vinu_tools SMA, used for the SUPPORTING-indicator columns
    (sma_5..sma_200) -- distinct from `_sma` above, which drives the
    must-condition's own crossing detection."""
    rows = pd.DataFrame({"close": close}).to_dict("records")
    col_name = f"sma_{period}"
    result = _sma_tools_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _ema_supporting(close: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"close": close}).to_dict("records")
    col_name = f"ema_{period}"
    result = _ema_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _atr_supporting(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    col_name = f"atr_{period}"
    result = _atr_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _roc_supporting(close: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"close": close}).to_dict("records")
    col_name = f"roc_{period}"
    result = _roc_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _stochastic_supporting(
    high: pd.Series, low: pd.Series, close: pd.Series, period: int, smooth: int
) -> tuple[pd.Series, pd.Series]:
    """One call with a non-matching `name` ("stochastic") -- vinu_tools'
    `stochastic.compute()` only returns a single named column if `name`
    matches one of its own output columns; passing a name that matches
    none of them makes it fall through to returning its *whole* internal
    dict (both %K and %D) from one computation, avoiding recomputing raw
    %K twice the way two separate named calls would."""
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    result = _stochastic_compute(rows, name="stochastic")
    k = pd.Series(result[f"stoch_k_{period}"], index=close.index)
    d = pd.Series(result[f"stoch_d_{period}"], index=close.index)
    return k, d


def _bollinger_supporting(close: pd.Series, period: int) -> tuple[pd.Series, pd.Series, pd.Series]:
    """One call, non-matching name -- same "get the whole dict back"
    trick as `_stochastic_supporting` above, applies identically to
    `bollinger.compute()`'s own upper/mid/lower dict."""
    rows = pd.DataFrame({"close": close}).to_dict("records")
    result = _bollinger_compute(rows, name="bollinger")
    upper = pd.Series(result[f"bb_upper_{period}"], index=close.index)
    mid = pd.Series(result[f"bb_mid_{period}"], index=close.index)
    lower = pd.Series(result[f"bb_lower_{period}"], index=close.index)
    return upper, mid, lower


def _aroon_supporting(high: pd.Series, low: pd.Series, period: int) -> tuple[pd.Series, pd.Series]:
    """Same non-matching-name trick again for `aroon.compute()`'s
    up/down pair."""
    rows = pd.DataFrame({"high": high, "low": low}).to_dict("records")
    result = _aroon_compute(rows, name="aroon")
    up = pd.Series(result["aroon_up"], index=high.index)
    down = pd.Series(result["aroon_down"], index=high.index)
    return up, down


def _macd_supporting(close: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Calls vinu_tools' shared internal `_macd()` directly (the same
    function its own `macd_signal.py` module calls) rather than the two
    separate `macd`/`macd_signal` wrapper modules, so EMA12/EMA26 aren't
    computed twice just to get line + signal. Histogram is the
    line-minus-signal derived step Section H flagged as not yet wired."""
    macd_line, signal_line = _macd_line_and_signal(close.tolist())
    macd_series = pd.Series(macd_line, index=close.index)
    signal_series = pd.Series(signal_line, index=close.index)
    histogram = macd_series - signal_series
    return macd_series, signal_series, histogram


def _cci_supporting(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    col_name = f"cci_{period}"
    result = _cci_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _williams_r_supporting(high: pd.Series, low: pd.Series, close: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    col_name = f"williams_r_{period}"
    result = _williams_r_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _supertrend_supporting(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    result = _supertrend_compute(rows, name="supertrend")
    return pd.Series(result["supertrend"], index=close.index)


def _high_low_spread_supporting(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    result = _high_low_spread_compute(rows, name="high_low_spread")
    return pd.Series(result["high_low_spread"], index=close.index)


def _open_close_return_supporting(open_: pd.Series, close: pd.Series) -> pd.Series:
    rows = pd.DataFrame({"open": open_, "close": close}).to_dict("records")
    result = _open_close_return_compute(rows, name="open_close_return")
    return pd.Series(result["open_close_return"], index=close.index)


def _momentum_supporting(close: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"close": close}).to_dict("records")
    col_name = f"momentum_{period}"
    result = _momentum_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _cmf_supporting(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int
) -> pd.Series:
    rows = pd.DataFrame(
        {"high": high, "low": low, "close": close, "volume": volume}
    ).to_dict("records")
    col_name = f"cmf_{period}"
    result = _cmf_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _ichimoku_supporting(
    high: pd.Series, low: pd.Series
) -> tuple[pd.Series, pd.Series, pd.Series, pd.Series]:
    """No PARAMS at all (fixed 9/26/52 periods -- see
    06-mistake-duplicated-indicator-logic.md), so the generic
    "non-matching name" one-call trick used for stochastic/bollinger/
    aroon above has nothing to silently diverge from here -- there's no
    override to ignore."""
    rows = pd.DataFrame({"high": high, "low": low}).to_dict("records")
    result = _ichimoku_compute(rows, name="ichimoku")
    tenkan = pd.Series(result["ichimoku_tenkan"], index=high.index)
    kijun = pd.Series(result["ichimoku_kijun"], index=high.index)
    senkou_a = pd.Series(result["ichimoku_senkou_a"], index=high.index)
    senkou_b = pd.Series(result["ichimoku_senkou_b"], index=high.index)
    return tenkan, kijun, senkou_a, senkou_b


def _parabolic_sar_supporting(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    rows = pd.DataFrame({"high": high, "low": low, "close": close}).to_dict("records")
    result = _parabolic_sar_compute(rows, name="parabolic_sar")
    return pd.Series(result["parabolic_sar"], index=close.index)


def _mfi_supporting(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, period: int
) -> pd.Series:
    rows = pd.DataFrame(
        {"high": high, "low": low, "close": close, "volume": volume}
    ).to_dict("records")
    col_name = f"mfi_{period}"
    result = _mfi_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=close.index)


def _vwap_supporting(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series, session_date: pd.Series
) -> pd.Series:
    """vinu_tools' `vwap` module is cumulative-since-first-row with no
    session reset (see all-possible-supporting-indicators.md's vwap_dist
    note) -- feeding it years of history would just produce a
    slow-drifting long-run average, not a meaningful "today's VWAP". This
    wrapper slices bars into per-session groups (by UTC calendar date
    from `bar_ts` -- this angle has no exchange-local trading-session
    machinery, so a UTC calendar day is the reset boundary used,
    consistent with how `trigger_time` elsewhere in this file already
    treats `bar_ts` as UTC) and calls vinu_tools' real `vwap` module
    independently per slice, so each session gets its own VWAP starting
    from 0 -- reusing vinu_tools' actual formula per session rather than
    reimplementing the money-weighted average math here."""
    out = pd.Series([None] * len(close), index=close.index, dtype=object)
    for day in session_date.unique():
        mask = (session_date == day).to_numpy()
        rows = pd.DataFrame({
            "high": high[mask], "low": low[mask], "close": close[mask], "volume": volume[mask],
        }).to_dict("records")
        result = _vwap_compute(rows, name="vwap")
        out.loc[mask] = result["vwap"]
    return pd.to_numeric(out, errors="coerce")


def _ad_line_supporting(
    high: pd.Series, low: pd.Series, close: pd.Series, volume: pd.Series
) -> pd.Series:
    rows = pd.DataFrame(
        {"high": high, "low": low, "close": close, "volume": volume}
    ).to_dict("records")
    result = _ad_line_compute(rows, name="accumulation_distribution_line")
    return pd.Series(result["accumulation_distribution_line"], index=close.index)


def _obv_supporting(close: pd.Series, volume: pd.Series) -> pd.Series:
    rows = pd.DataFrame({"close": close, "volume": volume}).to_dict("records")
    result = _obv_compute(rows, name="obv")
    return pd.Series(result["obv"], index=close.index)


def _volume_ratio_supporting(volume: pd.Series, period: int) -> pd.Series:
    rows = pd.DataFrame({"volume": volume}).to_dict("records")
    col_name = f"volume_ratio_{period}"
    result = _volume_ratio_compute(rows, name=col_name)
    return pd.Series(result[col_name], index=volume.index)


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
    open_ = bars["open"].astype(float) if "open" in bars.columns else None
    volume = bars["volume"].astype(float) if "volume" in bars.columns else None

    sma_fast = _sma(close, SMA_FAST)
    sma_slow = _sma(close, SMA_SLOW)
    adx = _adx(high, low, close, ADX_PERIOD)
    rsi = _rsi(close, RSI_PERIOD)
    volume_ratio = _volume_ratio_supporting(volume, VOLUME_AVG_PERIOD) if volume is not None else None

    # All vectorized, one pass each over the full bar history (column-wise
    # compute) -- per-trigger values are pulled out by position below when
    # assembling each row to write (row-wise write, per Decision 1's
    # one-row-per-trigger-event schema).
    sma_supporting = {p: _sma_supporting(close, p) for p in SMA_LENGTHS}
    ema_supporting = {p: _ema_supporting(close, p) for p in EMA_LENGTHS}
    # Derived from the sma/ema series just computed above -- arithmetic
    # on an already-computed value, not new indicator math (Section H).
    dist_from_sma = {p: (close - s) / s for p, s in sma_supporting.items()}
    dist_from_ema = {p: (close - s) / s for p, s in ema_supporting.items()}
    roc_supporting = {p: _roc_supporting(close, p) for p in ROC_LENGTHS}
    atr_14 = _atr_supporting(high, low, close, 14)
    stoch_k, stoch_d = _stochastic_supporting(high, low, close, STOCH_PERIOD, STOCH_SMOOTH)
    bb_upper, bb_mid, bb_lower = _bollinger_supporting(close, BOLLINGER_PERIOD)
    bollinger_band_width = (bb_upper - bb_lower) / bb_mid
    bollinger_percent_b = (close - bb_lower) / (bb_upper - bb_lower)
    macd_line, macd_signal, macd_histogram = _macd_supporting(close)
    aroon_up, aroon_down = _aroon_supporting(high, low, AROON_PERIOD)
    cci = _cci_supporting(high, low, close, CCI_PERIOD)
    williams_r = _williams_r_supporting(high, low, close, WILLIAMS_R_PERIOD)
    supertrend = _supertrend_supporting(high, low, close)
    high_low_spread = _high_low_spread_supporting(high, low, close)
    open_close_return = _open_close_return_supporting(open_, close) if open_ is not None else None
    momentum = _momentum_supporting(close, MOMENTUM_PERIOD)
    ichimoku_tenkan, ichimoku_kijun, ichimoku_senkou_a, ichimoku_senkou_b = _ichimoku_supporting(high, low)
    parabolic_sar = _parabolic_sar_supporting(high, low, close)
    obv = _obv_supporting(close, volume) if volume is not None else None
    cmf = _cmf_supporting(high, low, close, volume, CMF_PERIOD) if volume is not None else None
    mfi = _mfi_supporting(high, low, close, volume, MFI_PERIOD) if volume is not None else None
    ad_line = _ad_line_supporting(high, low, close, volume) if volume is not None else None

    # vwap_dist needs a session boundary to reset against -- only
    # computable when bar_ts is available (see _vwap_supporting).
    vwap_dist = None
    if volume is not None and "bar_ts" in bars.columns:
        session_date = pd.to_datetime(bars["bar_ts"], unit="s", utc=True).dt.date
        vwap = _vwap_supporting(high, low, close, volume, session_date)
        vwap_dist = (close - vwap) / vwap

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
            if volume_ratio is not None and not pd.isna(volume_ratio.iloc[i]):
                indicators["volume_vs_avg20"] = float(volume_ratio.iloc[i])
            for period, series in sma_supporting.items():
                if not pd.isna(series.iloc[i]):
                    indicators[f"sma_{period}"] = float(series.iloc[i])
            for period, series in ema_supporting.items():
                if not pd.isna(series.iloc[i]):
                    indicators[f"ema_{period}"] = float(series.iloc[i])
            for period, series in dist_from_sma.items():
                if not pd.isna(series.iloc[i]):
                    indicators[f"dist_from_sma_{period}"] = float(series.iloc[i])
            for period, series in dist_from_ema.items():
                if not pd.isna(series.iloc[i]):
                    indicators[f"dist_from_ema_{period}"] = float(series.iloc[i])
            for period, series in roc_supporting.items():
                if not pd.isna(series.iloc[i]):
                    indicators[f"roc_{period}"] = float(series.iloc[i])
            if not pd.isna(atr_14.iloc[i]):
                indicators["atr_14"] = float(atr_14.iloc[i])
            if not pd.isna(stoch_k.iloc[i]):
                indicators["stoch_k_14"] = float(stoch_k.iloc[i])
            if not pd.isna(stoch_d.iloc[i]):
                indicators["stoch_d_14"] = float(stoch_d.iloc[i])
            if not pd.isna(bollinger_band_width.iloc[i]):
                indicators["bollinger_band_width"] = float(bollinger_band_width.iloc[i])
            if not pd.isna(bollinger_percent_b.iloc[i]):
                indicators["bollinger_percent_b"] = float(bollinger_percent_b.iloc[i])
            if not pd.isna(macd_line.iloc[i]):
                indicators["macd_line"] = float(macd_line.iloc[i])
            if not pd.isna(macd_signal.iloc[i]):
                indicators["macd_signal"] = float(macd_signal.iloc[i])
            if not pd.isna(macd_histogram.iloc[i]):
                indicators["macd_histogram"] = float(macd_histogram.iloc[i])
            if not pd.isna(aroon_up.iloc[i]):
                indicators["aroon_up"] = float(aroon_up.iloc[i])
            if not pd.isna(aroon_down.iloc[i]):
                indicators["aroon_down"] = float(aroon_down.iloc[i])
            if not pd.isna(cci.iloc[i]):
                indicators["cci_20"] = float(cci.iloc[i])
            if not pd.isna(williams_r.iloc[i]):
                indicators["williams_r_14"] = float(williams_r.iloc[i])
            if not pd.isna(supertrend.iloc[i]):
                indicators["supertrend"] = float(supertrend.iloc[i])
            if not pd.isna(high_low_spread.iloc[i]):
                indicators["high_low_spread"] = float(high_low_spread.iloc[i])
            if open_close_return is not None and not pd.isna(open_close_return.iloc[i]):
                indicators["open_close_return"] = float(open_close_return.iloc[i])
            if not pd.isna(momentum.iloc[i]):
                indicators["momentum_10"] = float(momentum.iloc[i])
            if obv is not None and not pd.isna(obv.iloc[i]):
                indicators["obv"] = float(obv.iloc[i])
            if cmf is not None and not pd.isna(cmf.iloc[i]):
                indicators["cmf_20"] = float(cmf.iloc[i])
            if not pd.isna(ichimoku_tenkan.iloc[i]):
                indicators["ichimoku_tenkan"] = float(ichimoku_tenkan.iloc[i])
            if not pd.isna(ichimoku_kijun.iloc[i]):
                indicators["ichimoku_kijun"] = float(ichimoku_kijun.iloc[i])
            if not pd.isna(ichimoku_senkou_a.iloc[i]):
                indicators["ichimoku_senkou_a"] = float(ichimoku_senkou_a.iloc[i])
            if not pd.isna(ichimoku_senkou_b.iloc[i]):
                indicators["ichimoku_senkou_b"] = float(ichimoku_senkou_b.iloc[i])
            if not pd.isna(parabolic_sar.iloc[i]):
                indicators["parabolic_sar"] = float(parabolic_sar.iloc[i])
            if mfi is not None and not pd.isna(mfi.iloc[i]):
                indicators["mfi_14"] = float(mfi.iloc[i])
            if ad_line is not None and not pd.isna(ad_line.iloc[i]):
                indicators["accumulation_distribution_line"] = float(ad_line.iloc[i])
            if vwap_dist is not None and not pd.isna(vwap_dist.iloc[i]):
                indicators["vwap_dist"] = float(vwap_dist.iloc[i])

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
