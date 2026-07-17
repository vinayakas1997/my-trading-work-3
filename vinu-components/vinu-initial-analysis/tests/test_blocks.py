from vinu_initial_analysis.angles.session_time_analysis.blocks import (
    compute_correlation_by_session,
    compute_premarket_gap,
    compute_time_gaps,
)


def _make_event(ts: int, headline: str = "", session: str = "", price_change: float = 0.0):
    return {
        "ts": ts,
        "headline": headline,
        "session": session,
        "price_change_30m": price_change,
        "sentiment": "NEUTRAL",
        "impact_label": "low",
        "symbol": "AAPL",
        "article_id": f"a_{ts}",
        "computed_at": 1000000,
    }


def test_compute_time_gaps_empty():
    assert compute_time_gaps([]) == []


def test_compute_time_gaps_single():
    assert compute_time_gaps([_make_event(1000)]) == []


def test_compute_time_gaps_two():
    events = [_make_event(1000, "first"), _make_event(3700, "second")]
    gaps = compute_time_gaps(events)
    assert len(gaps) == 1
    assert gaps[0]["gap_hours"] == 0.75
    assert gaps[0]["before_ts"] == 1000
    assert gaps[0]["after_ts"] == 3700
    assert gaps[0]["before_headline"] == "first"
    assert gaps[0]["after_headline"] == "second"


def test_compute_time_gaps_multi():
    events = [
        _make_event(0, "a"),
        _make_event(3600, "b"),
        _make_event(7200, "c"),
    ]
    gaps = compute_time_gaps(events)
    assert len(gaps) == 2
    assert gaps[0]["gap_hours"] == 1.0
    assert gaps[1]["gap_hours"] == 1.0


def test_compute_premarket_gap_no_premarket():
    events = [_make_event(50000, "regular event", session="ny_regular")]
    gap = compute_premarket_gap(events)
    assert gap["gap_hours"] is not None


def test_compute_premarket_gap_with_premarket():
    market_open_ts = 14 * 3600
    events = [
        _make_event(40000, "late premarket", session="ny_premarket"),
        _make_event(35000, "early premarket", session="ny_premarket"),
    ]
    events[0]["ts"] = market_open_ts - 1800
    events[1]["ts"] = market_open_ts - 7200
    gap = compute_premarket_gap(events)
    assert gap["last_article_ts"] == market_open_ts - 1800


def test_compute_correlation_by_session_empty():
    result = compute_correlation_by_session([], [])
    assert result == {}
