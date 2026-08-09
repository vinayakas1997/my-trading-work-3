"""trend_lifecycle's own backtest glue code -- the two new pieces per the
decided design (04-enhancement-of-each-angle/30-trend_lifecycle.md SS3/SS5):

- `run_signal_outcome_backtest`: replays every historically-detected
  peak as if it were "the current peak" at its own bar_ts, generating
  the exact signal `compute()` would have produced at that moment
  (leak-free -- `find_similar`'s own `before_ts` filtering, already
  correct in the existing code, does the real work here), then joins it
  to that same peak's own REAL, already-known subsequent outcome
  (`drawdown_pct`, computed by `capture_all_peaks`/`_calculate_peak_outcomes`
  by scanning forward through the same real `bars` -- not a leak, since
  it's the peak's own recorded historical fact, never fed back into an
  earlier signal's matching).
- `run_confidence_calibration`: buckets those signal-outcome rows by
  `stated_confidence` and reports each bucket's real measured success
  rate -- the actual point of this enhancement, per the design doc's
  own framing.

Doesn't replay compute() step-by-step through the global config/
AngleStorage (compute() reads `load_config()` internally, a global,
process-wide coupling unsuitable for an isolated backtest) -- instead
calls the same lower-level, already-correct building blocks
(`detect_peaks`/`capture_all_peaks`/`find_similar`/`classify`/
`generate_signals`) directly against the full real `bars`, which is
possible without a leak specifically because `find_similar`'s `before_ts`
argument (not a temporal loop) is what actually enforces walk-forward
safety in the real code.
"""

from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles._tagging import tag_row
from vinu_initial_analysis.angles.trend_lifecycle.compute import _MIN_PEAK_DROP_PCT
from vinu_initial_analysis.angles.trend_lifecycle.lifecycle import classify
from vinu_initial_analysis.angles.trend_lifecycle.patterns import build_feature_matrix, find_similar
from vinu_initial_analysis.angles.trend_lifecycle.peaks import detect_peaks, detect_troughs, filter_alternating_inflections
from vinu_initial_analysis.angles.trend_lifecycle.signals import generate_signals
from vinu_initial_analysis.angles.trend_lifecycle.snapshots import capture_all_peaks, capture_all_troughs, compute_indicators

_DATE_ONLY_TAGS = ("day_of_week", "week_of_month", "month", "quarter")
_INTRADAY_TIMEFRAMES = ("15min", "1H", "4H")


def run_signal_outcome_backtest(
    symbol: str,
    bars: pd.DataFrame,
    time_format: str = "1D",
) -> pd.DataFrame:
    tf = time_format
    min_drop = _MIN_PEAK_DROP_PCT.get(tf, -3.0)

    close = bars["close"].astype(float)
    high = bars["high"].astype(float)
    low = bars["low"].astype(float)
    tr = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1
    ).max(axis=1)
    atr_series = tr.rolling(14).mean()

    peaks = detect_peaks(bars, min_drop_pct=min_drop, atr_series=atr_series)
    troughs = detect_troughs(bars, min_rise_pct=-min_drop, atr_series=atr_series)
    peaks, troughs = filter_alternating_inflections(peaks, troughs)
    if not peaks:
        return pd.DataFrame()

    indicators_df = compute_indicators(bars)
    all_snapshots = capture_all_peaks(bars, peaks, troughs, peaks, tf=tf, indicators_df=indicators_df)
    if not all_snapshots:
        return pd.DataFrame()

    for snap in all_snapshots:
        snap["time_format"] = tf
    library_df = pd.DataFrame(all_snapshots)
    use_session = tf in _INTRADAY_TIMEFRAMES

    X, lib_indices, norm_params = build_feature_matrix(library_df)
    rows: list[dict] = []
    sorted_snapshots = sorted(all_snapshots, key=lambda s: s["bar_idx"])

    for i, snap in enumerate(sorted_snapshots):
        query_ts = snap["bar_ts"]
        if X.shape[0] == 0:
            matches: list[dict] = []
        else:
            matches = find_similar(
                snap, library_df, X, lib_indices, k=5,
                norm_params=norm_params, before_ts=query_ts,
                session=snap.get("session") if use_session else None,
            )

        recent_peaks_sorted = sorted_snapshots[max(0, i - 2): i + 1]
        recent_troughs = [
            {"bar_ts": t["bar_ts"], "trough_close": t.get("trough_close")}
            for t in troughs if t["bar_ts"] < query_ts
        ][-3:]
        high_conf = sum(1 for m in matches if m.get("similarity", 0) > 0.85)
        drawdowns = [m.get("matched_drawdown_pct") for m in matches if m.get("matched_drawdown_pct") is not None]
        avg_dd = sum(drawdowns) / len(drawdowns) if drawdowns else None
        lifecycle_result = classify(recent_peaks_sorted, recent_troughs, high_conf, avg_dd)

        signals = generate_signals(matches, lifecycle_result, snap, symbol, tf, bar_ts=query_ts)

        actual_drawdown = snap.get("drawdown_pct")
        outcome_mature = bool(snap.get("outcome_mature"))
        for sig in signals:
            row = {
                "symbol": symbol,
                "bar_ts": query_ts,
                "session": snap.get("session"),
                "signal_type": sig.get("signal_type"),
                "stated_confidence": sig.get("confidence"),
                "suggested_exit_pct": sig.get("exit_threshold_pct"),
                "lifecycle_stage": lifecycle_result.get("stage"),
                "outcome_mature": outcome_mature,
                "actual_subsequent_drawdown_pct": actual_drawdown,
            }
            if sig.get("signal_type") == "book_profits" and outcome_mature and actual_drawdown is not None and sig.get("exit_threshold_pct") is not None:
                suggested = sig["exit_threshold_pct"]  # negative, e.g. -4.2
                # would_have_stopped_early: the real drop reached the suggested
                # stop level at some point (a stop at that level would have
                # triggered before the full move played out).
                row["would_have_stopped_early"] = bool(actual_drawdown <= suggested)
                # stop_would_have_helped: the real subsequent move was worse
                # than the suggested stop -- i.e. taking the stop beat holding.
                row["stop_would_have_helped"] = bool(actual_drawdown < suggested)
            else:
                row["would_have_stopped_early"] = None
                row["stop_would_have_helped"] = None
            row.update({k: v for k, v in tag_row(int(query_ts)).items() if k in _DATE_ONLY_TAGS})
            rows.append(row)

    return pd.DataFrame(rows)


def run_confidence_calibration(signal_outcomes: pd.DataFrame) -> pd.DataFrame:
    """Buckets `run_signal_outcome_backtest`'s output by stated confidence
    (0.1-wide bins) and reports each bucket's real measured success rate
    -- success = `stop_would_have_helped` for book_profits signals with a
    known (mature) outcome. Always carries `n`.
    """
    if signal_outcomes.empty or "signal_type" not in signal_outcomes.columns:
        return pd.DataFrame()
    scored = signal_outcomes[
        (signal_outcomes["signal_type"] == "book_profits")
        & signal_outcomes["stop_would_have_helped"].notna()
    ].copy()
    if scored.empty:
        return pd.DataFrame()

    scored["confidence_bucket_low"] = (scored["stated_confidence"] * 10).apply(lambda x: int(x) / 10.0)
    rows: list[dict] = []
    for bucket, group in scored.groupby("confidence_bucket_low"):
        rows.append({
            "confidence_bucket_low": bucket,
            "confidence_bucket_high": round(bucket + 0.1, 2),
            "n_signals": int(len(group)),
            "actual_success_rate": float(group["stop_would_have_helped"].mean()),
        })
    return pd.DataFrame(sorted(rows, key=lambda r: r["confidence_bucket_low"]))
