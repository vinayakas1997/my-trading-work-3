"""Point 3: the live indicator "detector".

Computes the same 51-indicator supporting snapshot Track 1's
signal_evidence angle computes for historical backfill
(vinu-initial-analysis/vinu_initial_analysis/angles/signal_evidence/
compute.py), but live, off a short trailing window of freshly-fetched
bars instead of a full backfill series -- reading only the last row.

No new indicator math: uses vinu_tools.compute.registry.apply_indicators
(the "blessed" generic entry point item #20.6 in
../02-open-questions-strategy-and-simulation.md found even Track 1's own
reference implementation doesn't use) for every indicator vinu_tools
already names as a feature, plus a small set of derived ratios
(dist_from_sma_*, dist_from_ema_*, bollinger width/percent_b, macd
histogram, vwap_dist) using the exact same formulas signal_evidence/
compute.py already uses -- kept in sync deliberately, not reinvented.

Design reference: .../reverse-engineering/04-live-detector-schema.md
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from vinu_tools.compute.registry import apply_indicators, warmup_bars_for_features

LOG = logging.getLogger(__name__)

SMA_LENGTHS = (5, 10, 20, 50, 100, 200)
EMA_LENGTHS = (5, 10, 20, 50, 100, 200)
ROC_LENGTHS = (5, 10, 20)

# The base feature set fetched via apply_indicators -- everything
# vinu_tools already names as a direct output column. Periods match
# Track 1's own defaults (../../how-to-use-29th-angle/
# 01-track1-how-it-works-today.md's knobs table) so a live snapshot and
# a historical signal_evidence row mean the same thing for the same
# indicator name.
BASE_FEATURE_NAMES: list[str] = (
    ["adx_14", "rsi_14"]
    + [f"sma_{p}" for p in SMA_LENGTHS]
    + [f"ema_{p}" for p in EMA_LENGTHS]
    + [f"roc_{p}" for p in ROC_LENGTHS]
    + ["atr_14", "stoch_k_14", "stoch_d_14"]
    + ["bb_upper_20", "bb_mid_20", "bb_lower_20"]
    + ["macd", "macd_signal"]
    + ["aroon_up", "aroon_down", "cci_20", "williams_r_14", "supertrend"]
    + ["high_low_spread", "open_close_return", "momentum_10"]
    + ["ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a", "ichimoku_senkou_b"]
    + ["parabolic_sar", "obv", "volume_ratio_20"]
    + ["cmf_20", "mfi_14", "accumulation_distribution_line"]
)

# vwap needs its own session-sliced call (see _vwap_dist below), not a
# plain apply_indicators request -- the raw vwap module is
# cumulative-since-first-row with no session reset.
_REQUIRED_COLUMNS = ("open", "high", "low", "close", "volume", "bar_ts")


def min_warmup_bars() -> int:
    """How many trailing bars the live fetch needs -- computed once from
    vinu_tools' own warmup_bars_for_features (already exists, already
    correct per indicator), not guessed. Callers should fetch at least
    this many bars for the timeframe they're polling."""
    return warmup_bars_for_features(BASE_FEATURE_NAMES)


def feature_window_bars(configured: int = 0) -> int:
    """Bars the live poller should fetch: never fewer than `min_warmup_bars()`, and `configured`
    when that is larger (logic-audit A8: slow EMAs need several times their period to converge)."""
    return max(min_warmup_bars(), int(configured or 0))


def _vwap_dist(bars: pd.DataFrame) -> float | None:
    """Mirrors signal_evidence/compute.py::_vwap_supporting exactly:
    session-date-sliced (UTC calendar date from bar_ts), vwap module
    called independently per session so each session resets to 0,
    rather than reimplementing the money-weighted-average formula here.
    A live fetch window is short enough that this is normally just the
    current session's slice, but sliced the same way regardless so a
    window spanning a session boundary still resets correctly."""
    if "volume" not in bars.columns or "bar_ts" not in bars.columns:
        return None
    from vinu_tools.compute.indicators.vwap.vwap import compute as _vwap_compute

    session_date = pd.to_datetime(bars["bar_ts"], unit="s", utc=True).dt.date
    last_day = session_date.iloc[-1]
    mask = (session_date == last_day).to_numpy()
    rows = bars.loc[mask, ["high", "low", "close", "volume"]].astype(float).to_dict("records")
    if not rows:
        return None
    result = _vwap_compute(rows, name="vwap")
    vwap_last = result["vwap"][-1]
    close_last = float(bars["close"].iloc[-1])
    if vwap_last is None or vwap_last == 0:
        return None
    return (close_last - vwap_last) / vwap_last


def compute_live_snapshot(bars: pd.DataFrame) -> dict[str, Any]:
    """The live equivalent of signal_evidence/compute.py's per-trigger
    supporting-indicator snapshot -- takes only the LAST row, since this
    is "what does this ticker look like right now," not a walk over
    historical crossings.

    `bars` must have open/high/low/close/volume/bar_ts columns (same
    contract signal_evidence's own `bars` DataFrame uses), covering at
    least `min_warmup_bars()` trailing rows.
    """
    missing = [c for c in ("open", "high", "low", "close", "volume") if c not in bars.columns]
    if missing:
        raise ValueError(f"compute_live_snapshot: bars missing required columns {missing}")
    if bars.empty:
        return {}

    rows = bars[["open", "high", "low", "close", "volume"]].astype(float).to_dict("records")
    computed_rows = apply_indicators(rows, BASE_FEATURE_NAMES)
    last = computed_rows[-1]

    snapshot: dict[str, Any] = {name: last.get(name) for name in BASE_FEATURE_NAMES}

    close_last = float(bars["close"].iloc[-1])
    for p in SMA_LENGTHS:
        sma = snapshot.get(f"sma_{p}")
        snapshot[f"dist_from_sma_{p}"] = (close_last - sma) / sma if sma else None
    for p in EMA_LENGTHS:
        ema = snapshot.get(f"ema_{p}")
        snapshot[f"dist_from_ema_{p}"] = (close_last - ema) / ema if ema else None

    bb_upper, bb_mid, bb_lower = snapshot.get("bb_upper_20"), snapshot.get("bb_mid_20"), snapshot.get("bb_lower_20")
    if bb_upper is not None and bb_mid and bb_lower is not None and (bb_upper - bb_lower) != 0:
        snapshot["bollinger_band_width"] = (bb_upper - bb_lower) / bb_mid
        snapshot["bollinger_percent_b"] = (close_last - bb_lower) / (bb_upper - bb_lower)
    else:
        snapshot["bollinger_band_width"] = None
        snapshot["bollinger_percent_b"] = None

    macd_line, macd_signal = snapshot.get("macd"), snapshot.get("macd_signal")
    snapshot["macd_line"] = macd_line
    snapshot["macd_histogram"] = (
        macd_line - macd_signal if macd_line is not None and macd_signal is not None else None
    )

    snapshot["volume_vs_avg20"] = snapshot.get("volume_ratio_20")
    snapshot["vwap_dist"] = _vwap_dist(bars)

    return snapshot


# item #10 (system-wide-audit-and-design/
# 02-open-questions-strategy-and-simulation.md): "cross-track disagreement
# as its own signal" needs Track 2's move-detection to run unconditionally,
# not only when a strategy's must-condition happens to fire -- otherwise a
# real move with no strategy watching for it is invisible forever, which is
# exactly the case this item cares about ("track2_only").
DEFAULT_MOVE_ATR_MULTIPLIER = 2.0


def detect_move(
    bars: pd.DataFrame,
    snapshot: dict[str, Any],
    multiplier: float = DEFAULT_MOVE_ATR_MULTIPLIER,
) -> dict[str, Any] | None:
    """Track 2's own already-documented move-detection floor (the "2xATR(14)
    move-detection floor" comment on `vinu_tools/compute/indicators/atr/
    atr.py`'s Decision 14 reference) -- a move is "real" when the latest
    closed bar's price change exceeds `multiplier` times ATR(14).

    Returns None (not a `move_detected: False` result) when there isn't
    enough history yet to judge -- fewer than 2 closes, or ATR not yet
    computable during warmup -- since "can't tell yet" must never be
    silently coerced into "no move happened," which would make an early,
    still-warming-up ticker look confirmed-quiet instead of unknown.
    """
    atr = snapshot.get("atr_14")
    if atr is None or atr <= 0 or len(bars) < 2:
        return None
    closes = bars["close"].astype(float)
    price_move = float(closes.iloc[-1] - closes.iloc[-2])
    threshold = multiplier * float(atr)
    direction = "up" if price_move > 0 else ("down" if price_move < 0 else "flat")
    return {
        "atr": float(atr),
        "price_move": price_move,
        "threshold": threshold,
        "move_detected": abs(price_move) > threshold,
        "direction": direction,
    }
