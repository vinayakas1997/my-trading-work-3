"""trend_session_structure's own backtest glue code -- the one addition
proposed by its design doc (04-enhancement-of-each-angle/31-trend_session_structure.md
SS3): a per-session breakdown of trend_lifecycle's (angle 30) new
signal-outcome/confidence-calibration data, once that data exists.
"does stated confidence actually track real accuracy differently by
session" -- the same "does session matter" question this angle already
asks of drawdown/recovery/similarity, applied to the new signal-outcome
data via the same premarket/regular/afterhours/closed taxonomy (not the
shared calendar-tagging scheme's session concept -- see
trend_lifecycle/backtest.py's own note on why these are different
fields).

Same thin-sample discipline as sessions.py's existing aggregation:
counts always reported, rates suppressed below the sample floor.
"""

from __future__ import annotations

import pandas as pd

_MIN_SIGNALS_FOR_RATE = 5
_SESSIONS = ["premarket", "regular", "afterhours", "closed"]


def aggregate_signal_outcomes_by_session(signal_outcomes: pd.DataFrame) -> pd.DataFrame:
    """Takes trend_lifecycle.backtest.run_signal_outcome_backtest()'s
    output and reports, per session, how many book_profits signals fired,
    their average stated confidence, and their real measured success
    rate (`stop_would_have_helped`) -- suppressed below
    `_MIN_SIGNALS_FOR_RATE` mature signals, same "don't report a rate off
    almost nothing" discipline as sessions.py's `_MIN_SAMPLE`.
    """
    if signal_outcomes.empty or "signal_type" not in signal_outcomes.columns:
        return pd.DataFrame()

    scored = signal_outcomes[
        (signal_outcomes["signal_type"] == "book_profits")
        & signal_outcomes["session"].notna()
    ].copy()
    if scored.empty:
        return pd.DataFrame()

    rows: list[dict] = []
    for session in _SESSIONS:
        s = scored[scored["session"] == session]
        if s.empty:
            continue
        mature = s[s["stop_would_have_helped"].notna()]
        n_signals = int(len(s))
        n_mature = int(len(mature))
        row: dict = {
            "session": session,
            "n_signals": n_signals,
            "n_mature_signals": n_mature,
            "meets_floor": n_mature >= _MIN_SIGNALS_FOR_RATE,
            "avg_stated_confidence": round(float(s["stated_confidence"].mean()), 4) if n_signals else None,
            "measured_success_rate": None,
        }
        if n_mature >= _MIN_SIGNALS_FOR_RATE:
            row["measured_success_rate"] = round(float(mature["stop_would_have_helped"].mean()), 4)
        rows.append(row)

    return pd.DataFrame(rows)
