"""The analysis reads a frozen copy of one ticker's news for one range, not the live news store.

Same input gives the same result; an outage or a revision in the live store during a long read cannot change an analysis that
already has its input; deleting a copy is always safe (it is rebuilt)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from vinu_initial_analysis.clients.news_snapshot import FINAL_GRACE_SEC, LIVE_TTL_SEC, SnapshotNewsClient

T0 = 1_800_000_000


class FakeNews:
    def __init__(self, rows):
        self.rows = rows
        self.calls = 0
        self.fail = False

    def get_ticker_news(self, symbol, days=7, *, from_ts=None, to_ts=None, limit=500):
        self.calls += 1
        if self.fail:
            raise ConnectionError("news down")
        return [dict(r) for r in self.rows]

    def get_articles_since(self, *a, **k):
        return []


ROWS = [
    {"id": "a", "headline": "Apple beats", "sort_ts": T0 - 5000, "sentiment": "BULLISH", "sentiment_score": 3,
     "finbert_score": None, "tickers": '["AAPL"]', "story_sources": ["BENZINGA"], "story_n_sources": 1, "is_lead": 1},
    {"id": "b", "headline": "Apple falls", "sort_ts": T0 - 9000, "sentiment": "BEARISH", "sentiment_score": -2,
     "finbert_score": 0.4, "tickers": '["AAPL"]', "story_sources": ["BENZINGA", "CNBC"], "story_n_sources": 2, "is_lead": 1},
]


class Clock:
    def __init__(self, t):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def parts(tmp_path: Path):
    inner, clock = FakeNews(ROWS), Clock(T0)
    return inner, clock, SnapshotNewsClient(inner, tmp_path / "news_inputs", clock=clock)


def test_a_closed_range_is_read_once_and_then_served_from_the_copy(parts):
    inner, clock, snap = parts
    first = snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    clock.t += 10 * 86_400
    second = snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    assert inner.calls == 1 and first == second


def test_the_copy_has_the_same_rows_and_columns_with_plain_python_values(parts):
    inner, _, snap = parts
    snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    inner.fail = True                                         # now only the copy can answer
    got = snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    assert got == ROWS                                        # None stays None, lists stay lists, ints stay ints
    assert got[0]["finbert_score"] is None and got[1]["story_sources"] == ["BENZINGA", "CNBC"]


def test_a_live_outage_cannot_change_an_analysis_that_has_its_copy(parts):
    inner, _, snap = parts
    snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    inner.fail = True
    assert snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000) == ROWS
    with pytest.raises(ConnectionError):                      # a range with no copy still fails loudly, never "no news"
        snap.get_ticker_news("AAPL", from_ts=T0 - 700_000, to_ts=T0 - 500_000)


def test_a_range_that_reaches_the_present_is_rebuilt_when_old(parts):
    inner, clock, snap = parts
    snap.get_ticker_news("AAPL", from_ts=T0 - 100_000, to_ts=None)
    clock.t += LIVE_TTL_SEC - 10
    snap.get_ticker_news("AAPL", from_ts=T0 - 100_000, to_ts=None)
    assert inner.calls == 1
    clock.t += 60
    snap.get_ticker_news("AAPL", from_ts=T0 - 100_000, to_ts=None)
    assert inner.calls == 2


def test_the_manifest_says_how_current_the_copy_is(parts, tmp_path):
    _, _, snap = parts
    snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    (m,) = snap.list_snapshots()
    assert m["symbol"] == "AAPL" and m["n_rows"] == 2 and m["data_through"] == T0 - 5000
    assert m["built_at"] == T0 and m["schema_version"] == 1 and "finbert_score" in m["columns"]


def test_an_empty_answer_is_never_kept(parts):
    inner, _, snap = parts
    inner.rows = []
    assert snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000) == []
    assert snap.list_snapshots() == []                         # it could have been an outage; ask again next time
    inner.rows = ROWS
    assert len(snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)) == 2


def test_a_copy_of_an_older_schema_is_rebuilt(parts, tmp_path):
    inner, _, snap = parts
    snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    mp = next((tmp_path / "news_inputs" / "AAPL").glob("*.json"))
    data = json.loads(mp.read_text())
    data["schema_version"] = 0
    mp.write_text(json.dumps(data))
    snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    assert inner.calls == 2


def test_deleting_a_tickers_copies_is_safe_and_the_next_read_rebuilds(parts):
    inner, _, snap = parts
    snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)
    snap.get_ticker_news("AAPL", from_ts=T0 - 900_000, to_ts=T0 - 800_000)
    assert snap.delete("AAPL") == 2 and snap.list_snapshots() == [] and snap.delete("AAPL") == 0
    assert len(snap.get_ticker_news("AAPL", from_ts=T0 - 400_000, to_ts=T0 - 200_000)) == 2
    with pytest.raises(ValueError):
        snap.delete("../x")


def test_a_relative_window_is_not_frozen(parts):
    inner, _, snap = parts
    snap.get_ticker_news("AAPL", days=7)
    snap.get_ticker_news("AAPL", days=7)
    assert inner.calls == 2 and snap.list_snapshots() == []
