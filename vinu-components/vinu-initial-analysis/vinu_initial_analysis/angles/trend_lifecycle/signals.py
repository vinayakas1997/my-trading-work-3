"""Trade signal generation — produce actionable exit/entry signals from pattern matches.

Outputs concrete percentage thresholds: "Set trailing stop at -4% from peak."
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime, timezone


def generate_signals(
    matches: list[dict],
    lifecycle: dict,
    snapshot: dict | None,
    symbol: str,
    time_format: str,
    bar_ts: int | None = None,
) -> list[dict]:
    """Generate trade signals from pattern matches and lifecycle stage.

    Returns list of signal dicts, each with signal_type, confidence, and suggested_action.
    """
    now = datetime.now(timezone.utc).isoformat()
    signals = []

    if not matches:
        signals.append({
            "type": "signal",
            "analysis_at": now,
            "bar_ts": bar_ts,
            "signal_type": "insufficient_data",
            "confidence": 0.0,
            "suggested_action": "Not enough historical patterns to generate a signal.",
            "avg_drawdown_pct": None,
            "exit_threshold_pct": None,
        })
        return signals

    drawdowns = [m.get("matched_drawdown_pct") for m in matches if m.get("matched_drawdown_pct") is not None]
    if not drawdowns:
        signals.append({
            "type": "signal",
            "analysis_at": now,
            "bar_ts": bar_ts,
            "signal_type": "no_outcome_data",
            "confidence": 0.0,
            "suggested_action": "Matched patterns found but no historical drawdown data available yet.",
            "avg_drawdown_pct": None,
            "exit_threshold_pct": None,
        })
        return signals

    avg_dd = sum(drawdowns) / len(drawdowns)
    min_dd = min(drawdowns)
    max_dd = max(drawdowns)
    high_conf = sum(1 for m in matches if m.get("similarity", 0) > 0.85)
    peak_price = snapshot.get("peak_close") if snapshot else None
    avg_similarity = sum(m.get("similarity", 0) for m in matches) / len(matches)

    life_stage = lifecycle.get("stage", "unknown") if lifecycle else "unknown"
    life_risk = lifecycle.get("risk", "unknown") if lifecycle else "unknown"

    if life_stage in ("topping", "downtrend") or life_risk == "high":
        exit_pct = round(abs(avg_dd) * 0.5, 1)
        confidence = min(0.95, 0.5 + high_conf * 0.08 + avg_similarity * 0.2)
        if avg_dd < -8:
            action = f"Set trailing stop at -{exit_pct}% from peak"
            if peak_price:
                stop_price = round(peak_price * (1 - exit_pct / 100), 2)
                action += f" (${stop_price})"
            action += f". Historical similar peaks dropped avg {round(abs(avg_dd), 1)}% (range: {round(abs(min_dd), 1)}% to {round(abs(max_dd), 1)}%)."
        elif avg_dd < -4:
            action = f"Monitor closely. Set alert at -{exit_pct}% from peak"
            if peak_price:
                stop_price = round(peak_price * (1 - exit_pct / 100), 2)
                action += f" (${stop_price})"
            action += f". Similar peaks dropped avg {round(abs(avg_dd), 1)}%."
        else:
            action = f"Low drawdown risk estimated ({round(abs(avg_dd), 1)}%). Continue holding but monitor."
            confidence = min(0.6, confidence)

        signals.append({
            "type": "signal",
            "analysis_at": now,
            "bar_ts": bar_ts,
            "signal_type": "book_profits",
            "confidence": round(confidence, 2),
            "suggested_action": action,
            "avg_drawdown_pct": round(avg_dd, 2),
            "exit_threshold_pct": round(-exit_pct, 1),
            "lifecycle_stage": life_stage,
            "n_high_confidence_matches": high_conf,
        })

        re_entry = _re_entry_signal(snapshot, lifecycle, bar_ts=bar_ts)
        if re_entry:
            signals.append(re_entry)

    elif life_stage == "uptrend":
        signals.append({
            "type": "signal",
            "analysis_at": now,
            "bar_ts": bar_ts,
            "signal_type": "hold",
            "confidence": 0.7,
            "suggested_action": "Trend intact. Hold current position. Reassess at next peak signal.",
            "avg_drawdown_pct": round(avg_dd, 2) if drawdowns else None,
            "exit_threshold_pct": None,
            "lifecycle_stage": life_stage,
            "n_high_confidence_matches": high_conf,
        })

    elif life_stage == "basing":
        signals.append({
            "type": "signal",
            "analysis_at": now,
            "bar_ts": bar_ts,
            "signal_type": "accumulate",
            "confidence": 0.6,
            "suggested_action": "Basing phase detected. Consider accumulating on dips. Final confirmation needed above recent peak.",
            "avg_drawdown_pct": round(avg_dd, 2) if drawdowns else None,
            "exit_threshold_pct": None,
            "lifecycle_stage": life_stage,
            "n_high_confidence_matches": high_conf,
        })

    else:
        signals.append({
            "type": "signal",
            "analysis_at": now,
            "bar_ts": bar_ts,
            "signal_type": "manual_review",
            "confidence": 0.3,
            "suggested_action": f"Mixed signals. Lifecycle: {life_stage}. Review chart manually before acting.",
            "avg_drawdown_pct": round(avg_dd, 2) if drawdowns else None,
            "exit_threshold_pct": None,
            "lifecycle_stage": life_stage,
            "n_high_confidence_matches": high_conf,
        })

    return signals


def _re_entry_signal(snapshot: dict | None, lifecycle: dict, bar_ts: int | None = None) -> dict | None:
    """Generate re-entry signal if conditions are met."""
    if lifecycle.get("stage") != "downtrend":
        return None
    return {
        "type": "signal",
        "analysis_at": datetime.now(timezone.utc).isoformat(),
        "bar_ts": bar_ts,
        "signal_type": "re_entry",
        "confidence": 0.4,
        "suggested_action": f"Re-entry signal: wait for price to recover above SMA_50 with RSI > 40. Current stage: {lifecycle.get('stage')}.",
        "avg_drawdown_pct": None,
        "exit_threshold_pct": None,
        "lifecycle_stage": lifecycle.get("stage"),
        "n_high_confidence_matches": 0,
    }
