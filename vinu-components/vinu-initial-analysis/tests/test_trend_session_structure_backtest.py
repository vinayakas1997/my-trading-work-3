from __future__ import annotations

import pandas as pd

from vinu_initial_analysis.angles.trend_session_structure.backtest import (
    aggregate_signal_outcomes_by_session,
)


def _make_signal_outcomes(rows: list[dict]) -> pd.DataFrame:
    defaults = {"signal_type": "book_profits", "stated_confidence": 0.5, "session": "regular"}
    return pd.DataFrame([{**defaults, **r} for r in rows])


def test_aggregates_per_session_with_thin_sample_suppression():
    rows = []
    for i in range(6):
        rows.append({"session": "regular", "stated_confidence": 0.6, "stop_would_have_helped": i % 2 == 0})
    for i in range(3):
        rows.append({"session": "premarket", "stated_confidence": 0.4, "stop_would_have_helped": True})
    df = aggregate_signal_outcomes_by_session(_make_signal_outcomes(rows))

    regular = df[df["session"] == "regular"].iloc[0]
    assert regular["n_signals"] == 6
    assert bool(regular["meets_floor"]) is True
    assert regular["measured_success_rate"] == 0.5

    premarket = df[df["session"] == "premarket"].iloc[0]
    assert premarket["n_signals"] == 3
    assert bool(premarket["meets_floor"]) is False
    # None -> NaN once the column round-trips through a float64 DataFrame column
    assert pd.isna(premarket["measured_success_rate"])


def test_ignores_non_book_profits_signals():
    rows = [{"signal_type": "hold", "session": "regular", "stop_would_have_helped": None}]
    df = aggregate_signal_outcomes_by_session(_make_signal_outcomes(rows))
    assert df.empty


def test_empty_on_empty_input():
    assert aggregate_signal_outcomes_by_session(pd.DataFrame()).empty
