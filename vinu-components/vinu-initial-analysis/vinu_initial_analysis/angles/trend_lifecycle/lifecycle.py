"""Lifecycle stage classification — uptrend / topping / downtrend / basing.

Determined by analyzing the sequence of recent peaks and troughs
and their indicator profiles.
"""

from __future__ import annotations


def classify(
    recent_peaks: list[dict],
    recent_troughs: list[dict],
    n_matches_high_conf: int,
    avg_matched_dd_pct: float | None,
) -> dict:
    """Classify the current lifecycle stage based on recent extrema and pattern matches.

    Returns dict with stage name, description, and risk level.
    """
    peak_trend = _compute_trend(recent_peaks, "peak")
    trough_trend = _compute_trend(recent_troughs, "trough")

    if peak_trend == "higher" and trough_trend == "higher":
        stage = "uptrend"
        risk = "low"
        desc = "Higher highs and higher lows. Trend is intact."
    elif peak_trend == "lower" and trough_trend == "lower":
        stage = "downtrend"
        risk = "high"
        desc = "Lower highs and lower lows. Trend is broken."
    elif peak_trend == "higher" and trough_trend == "lower":
        stage = "topping"
        risk = "high"
        desc = "Higher highs but lower lows. Potential trend exhaustion / reversal pattern."
    elif peak_trend == "lower" and trough_trend == "higher":
        stage = "basing"
        risk = "low"
        desc = "Lower highs but higher lows. Consolidation / accumulation phase."
    else:
        stage = "sideways"
        risk = "medium"
        desc = "No clear directional pattern. Sideways movement."

    if n_matches_high_conf >= 3 and avg_matched_dd_pct is not None and avg_matched_dd_pct < -5:
        risk = "high"
        desc += f" Pattern library shows {n_matches_high_conf} similar peaks with avg {round(avg_matched_dd_pct, 1)}% drawdown."

    return {
        "type": "lifecycle",
        "stage": stage,
        "risk": risk,
        "description": desc,
        "n_recent_peaks": len(recent_peaks),
        "n_recent_troughs": len(recent_troughs),
        "peak_trend": peak_trend,
        "trough_trend": trough_trend,
    }


def _compute_trend(extrema: list[dict], key: str) -> str:
    """Determine if the sequence of extrema is higher, lower, or flat."""
    if len(extrema) < 2:
        return "insufficient"
    # Trough snapshots store the close as "peak_close"; fallback gracefully
    prices = []
    for e in extrema:
        if key == "peak":
            prices.append(e.get("peak_close"))
        else:
            v = e.get("trough_close")
            if v is None:
                v = e.get("peak_close")
            prices.append(v)
    prices = [p for p in prices if p is not None]
    if len(prices) < 2:
        return "insufficient"
    recent = prices[-1]
    previous = prices[-2]
    diff_pct = (recent - previous) / previous * 100
    if diff_pct > 1.0:
        return "higher"
    elif diff_pct < -1.0:
        return "lower"
    else:
        return "flat"
