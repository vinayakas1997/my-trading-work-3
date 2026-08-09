from __future__ import annotations

from typing import Any

import pandas as pd


_SENTIMENT_WEIGHTS: dict[str, float] = {
    "BULLISH": 1.0,
    "BEARISH": 1.0,
    "NEUTRAL": 0.3,
}


def get_drawdowns(
    symbol: str,
    candles: list[dict],
    from_ts: int | None = None,
    to_ts: int | None = None,
    drop_threshold_pct: float = -3.0,
    lookback_hours: int = 24,
) -> list[dict[str, Any]]:
    sorted_c = sorted(
        [c for c in candles
         if (from_ts is None or c.get("bar_ts", 0) >= from_ts)
         and (to_ts is None or c.get("bar_ts", 0) <= to_ts)],
        key=lambda x: x.get("bar_ts", 0),
    )
    if len(sorted_c) < 2:
        return []

    drawdowns = []
    in_drawdown = False
    peak_idx = 0
    trough_data: dict = {}

    for i in range(1, len(sorted_c)):
        if not in_drawdown:
            close_t = sorted_c[i].get("close", 0)
            peak_candidate_idx = peak_idx
            for j in range(peak_idx, i + 1):
                if sorted_c[j].get("high", 0) >= sorted_c[peak_candidate_idx].get("high", 0):
                    peak_candidate_idx = j
            if peak_candidate_idx > peak_idx:
                peak_idx = peak_candidate_idx
            peak_price = sorted_c[peak_idx].get("high", 0)
            drop = (close_t - peak_price) / peak_price * 100
            if drop <= drop_threshold_pct:
                in_drawdown = True
                trough_data = {
                    "symbol": symbol,
                    "peak_ts": sorted_c[peak_idx]["bar_ts"],
                    "peak_price": peak_price,
                    "peak_idx": peak_idx,
                    "trough_ts": sorted_c[i]["bar_ts"],
                    "trough_price": close_t,
                    "drop_pct": round(drop, 2),
                    "trough_idx": i,
                }
        else:
            close_t = sorted_c[i].get("close", 0)
            current_drop = (close_t - trough_data["peak_price"]) / trough_data["peak_price"] * 100
            if current_drop < trough_data["drop_pct"]:
                trough_data["drop_pct"] = round(current_drop, 2)
                trough_data["trough_price"] = close_t
                trough_data["trough_ts"] = sorted_c[i]["bar_ts"]
                trough_data["trough_idx"] = i
            peak_price = sorted_c[i].get("high", 0)
            if peak_price > trough_data["peak_price"]:
                ts_lookback = trough_data["peak_ts"] - lookback_hours * 3600
                drawdowns.append({
                    "symbol": symbol,
                    "peak_ts": trough_data["peak_ts"],
                    "trough_ts": trough_data["trough_ts"],
                    "drop_pct": trough_data["drop_pct"],
                    "peak_price": trough_data["peak_price"],
                    "trough_price": trough_data["trough_price"],
                    "lookback_from_ts": ts_lookback,
                })
                in_drawdown = False
                peak_idx = i
                trough_data = {}

    if in_drawdown:
        ts_lookback = trough_data["peak_ts"] - lookback_hours * 3600
        drawdowns.append({
            "symbol": symbol,
            "peak_ts": trough_data["peak_ts"],
            "trough_ts": trough_data["trough_ts"],
            "drop_pct": trough_data["drop_pct"],
            "peak_price": trough_data["peak_price"],
            "trough_price": trough_data["trough_price"],
            "lookback_from_ts": ts_lookback,
        })

    return drawdowns


def _compute_event_weight(event: dict) -> float:
    score = abs(event.get("price_change_30m", 0) or 0)
    sentiment = event.get("sentiment", "NEUTRAL").upper()
    weight = _SENTIMENT_WEIGHTS.get(sentiment, 0.3)
    return score * weight


def attribute_drawdown(
    symbol: str,
    peak_ts: int,
    trough_ts: int,
    events: list[dict],
    market_returns: list[dict] | None = None,
) -> dict[str, Any]:
    from vinu_initial_analysis.angles._market_hours import IMPACT_WINDOWS

    relevant_events = [
        e for e in events
        if e.get("symbol", "").upper() == symbol.upper()
        and peak_ts <= e.get("ts", 0) <= trough_ts
    ]

    n_events = len(relevant_events)
    if n_events == 0:
        return {
            "peak_ts": peak_ts,
            "trough_ts": trough_ts,
            "drop_pct": 0.0,
            "attribution": {
                "news_driven_pct": 0.0,
                "market_beta_pct": 0.0,
                "unexplained_pct": 1.0,
                "contributing_events": [],
            },
        }

    total_weighted_score = sum(_compute_event_weight(ev) for ev in relevant_events)

    contributing = []
    for ev in relevant_events:
        w = _compute_event_weight(ev)
        contributing.append({
            "headline": ev.get("headline", ""),
            "attribution_pct": round(w / total_weighted_score, 4) if total_weighted_score > 0 else 0.0,
            "sentiment": ev.get("sentiment", "NEUTRAL"),
            "impact_label": ev.get("impact_label", "low"),
        })

    baseline_score = 0.1 * n_events  # normalize by event count
    news_pct = total_weighted_score / (total_weighted_score + baseline_score + 1.0)
    news_pct = min(news_pct, 0.95)
    market_pct = 0.0 if market_returns is None else 0.2
    unexplained_pct = 1.0 - news_pct - market_pct

    return {
        "peak_ts": peak_ts,
        "trough_ts": trough_ts,
        "drop_pct": 0.0,
        "attribution": {
            "news_driven_pct": round(news_pct, 4),
            "market_beta_pct": round(market_pct, 4),
            "unexplained_pct": round(max(unexplained_pct, 0), 4),
            "contributing_events": sorted(contributing, key=lambda x: x["attribution_pct"], reverse=True),
        },
    }


def atr_pct_series(bars: pd.DataFrame, period: int = 14) -> list[float | None]:
    """Rolling, trailing-only ATR(period) as a percentage of close price.

    Reuses the real vinu_tools ATR indicator (plain SMA of true range, not
    Wilder's exact recursive smoothing formula -- the decided design's
    emphasis was on the period (14, "Wilder's standard convention") and the
    rolling/no-lookahead property, both satisfied here; see
    06-implementation-of-each-angles/06-drawdown_deep_dive/00-plan.md).
    """
    from vinu_tools.compute.indicators.atr.atr import compute as atr_compute

    rows = bars[["high", "low", "close"]].astype(float).to_dict("records")
    col_name = f"atr_{period}"
    result = atr_compute(rows, name=col_name)
    atr_values = result[col_name]
    close = bars["close"].astype(float).tolist()
    return [
        (a / c * 100) if a is not None and c else None
        for a, c in zip(atr_values, close)
    ]


def _shape_checkpoints(sub_bars: pd.DataFrame, start_price: float, end_price: float) -> dict[str, Any]:
    """First candle (0-based within sub_bars) whose close crosses 25/50/75%
    cumulative progress from start_price to end_price. Works for both a
    falling formation phase (end < start) and a rising recovery phase
    (end > start) since the sign of `total` handles direction.
    """
    total = end_price - start_price
    checkpoints: dict[str, Any] = {}
    for pct, label in ((0.25, "25%"), (0.5, "50%"), (0.75, "75%")):
        found = None
        if total != 0:
            for idx, close in enumerate(sub_bars["close"].astype(float).tolist()):
                progress = (close - start_price) / total
                if progress >= pct:
                    found = {"candle": idx, "price": close}
                    break
        checkpoints[label] = found
    return checkpoints


def detect_drawdown_episodes(
    symbol: str,
    bars: pd.DataFrame,
    k: float,
    news: list[dict] | None = None,
    min_threshold_pct: float = -0.5,
    atr_period: int = 14,
) -> list[dict[str, Any]]:
    """State-machine scan for every drawdown episode (peak -> trough ->
    recovery), with an ATR-adaptive threshold, shape checkpoints, and a
    formation/recovery news split -- per
    04-enhancement-of-each-angle/06-drawdown_deep_dive.md.

    Not a walk-forward loop: this returns a variable number of episode
    rows (data-dependent), not one row per candle, so it isn't run
    through run_walk_forward -- see 06-implementation-of-each-angles/
    06-drawdown_deep_dive/00-plan.md.

    Rolling-peak and recovery-trigger logic (a later candle's high
    exceeding the *original* peak's high) is the same mechanism
    `get_drawdowns` already used -- extended here with the ATR-adaptive
    threshold and full lifecycle tracking `get_drawdowns` never had.
    """
    bars = bars.reset_index(drop=True)
    n = len(bars)
    if n < 2:
        return []

    bar_ts = bars["bar_ts"].astype(int).tolist()
    high = bars["high"].astype(float).tolist()
    close = bars["close"].astype(float).tolist()
    atr_pct = atr_pct_series(bars, period=atr_period)
    news = news or []

    def threshold_for(idx: int) -> float | None:
        a = atr_pct[idx]
        if a is None:
            return None
        return -max(k * a, abs(min_threshold_pct))

    def news_in_range(start_ts: int, end_ts: int) -> list[dict]:
        return [
            e for e in news
            if str(e.get("symbol", "")).upper() == symbol.upper()
            and start_ts <= e.get("ts", e.get("published_at", 0)) <= end_ts
        ]

    def finalize(p_idx: int, t_idx: int, r_idx: int | None) -> dict[str, Any]:
        peak_price = high[p_idx]
        trough_price = close[t_idx]
        drop_pct = round((trough_price - peak_price) / peak_price * 100, 4)
        duration_to_trough = t_idx - p_idx
        trough_speed = round(drop_pct / duration_to_trough, 4) if duration_to_trough else None
        atr_at_peak = atr_pct[p_idx]
        threshold_used = threshold_for(p_idx)

        formation_sub = bars.iloc[p_idx : t_idx + 1]
        row: dict[str, Any] = {
            "symbol": symbol,
            "status": "recovered" if r_idx is not None else "open",
            "peak_ts": bar_ts[p_idx],
            "peak_price": peak_price,
            "atr_pct_at_peak": round(atr_at_peak, 4) if atr_at_peak is not None else None,
            "threshold_pct_used": round(threshold_used, 4) if threshold_used is not None else None,
            "trough_ts": bar_ts[t_idx],
            "trough_price": trough_price,
            "drop_pct": drop_pct,
            "duration_to_trough": duration_to_trough,
            "trough_speed": trough_speed,
            "formation_checkpoints": _shape_checkpoints(formation_sub, peak_price, trough_price),
            "formation_news": news_in_range(bar_ts[p_idx], bar_ts[t_idx]),
        }

        if r_idx is not None:
            recovery_price = close[r_idx]
            recovery_gain_pct = round((recovery_price - trough_price) / trough_price * 100, 4)
            duration_to_recovery = r_idx - t_idx
            recovery_speed = round(recovery_gain_pct / duration_to_recovery, 4) if duration_to_recovery else None
            recovery_sub = bars.iloc[t_idx : r_idx + 1]
            row.update({
                "recovery_ts": bar_ts[r_idx],
                "recovery_price": recovery_price,
                "recovery_gain_pct": recovery_gain_pct,
                "duration_to_recovery": duration_to_recovery,
                "recovery_speed": recovery_speed,
                "recovery_checkpoints": _shape_checkpoints(recovery_sub, trough_price, recovery_price),
                "recovery_news": news_in_range(bar_ts[t_idx], bar_ts[r_idx]),
            })
        else:
            row.update({
                "recovery_ts": None,
                "recovery_price": None,
                "recovery_gain_pct": None,
                "duration_to_recovery": None,
                "recovery_speed": None,
                "recovery_checkpoints": None,
                "recovery_news": [],
            })
        return row

    # Peak tracking must start once ATR has real values, not at index 0 --
    # a peak candle that predates ATR's own 14-period warmup would have
    # threshold_for(peak_idx) stuck at None forever (ATR is looked up AT
    # THE PEAK, per the decided atr_pct_at_peak semantics, not at the
    # evaluation candle), permanently blocking detection from that peak
    # onward. Same min_observations-style discipline used everywhere else
    # in this project (ARIMA/DLinear/Chronos all require real data before
    # evaluation begins) -- found via a real synthetic-data test, not
    # theoretical.
    first_valid = next((idx for idx, a in enumerate(atr_pct) if a is not None), None)
    if first_valid is None:
        return []

    episodes: list[dict[str, Any]] = []
    peak_idx = first_valid
    in_drawdown = False
    trough_idx: int | None = None
    trough_price: float | None = None

    for i in range(first_valid + 1, n):
        if not in_drawdown:
            for j in range(peak_idx, i + 1):
                if high[j] >= high[peak_idx]:
                    peak_idx = j
            threshold = threshold_for(peak_idx)
            if threshold is not None:
                peak_price = high[peak_idx]
                drop = (close[i] - peak_price) / peak_price * 100
                if drop <= threshold:
                    in_drawdown = True
                    trough_idx = i
                    trough_price = close[i]
        else:
            if close[i] < trough_price:  # type: ignore[operator]
                trough_price = close[i]
                trough_idx = i
            if high[i] > high[peak_idx]:
                episodes.append(finalize(peak_idx, trough_idx, i))  # type: ignore[arg-type]
                in_drawdown = False
                peak_idx = i

    if in_drawdown:
        episodes.append(finalize(peak_idx, trough_idx, None))  # type: ignore[arg-type]

    return episodes
