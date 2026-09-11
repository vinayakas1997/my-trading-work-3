from __future__ import annotations

import pytest

from vinu_screener.pipeline.candidate import Candidate
from vinu_screener.pipeline.pipeline import PipelineResult
from vinu_screener.rankers.snapshot_store import RankedSnapshotStore


@pytest.fixture
def store():
    return RankedSnapshotStore(":memory:")


def _result(symbols_scores: list[tuple[str, float]]) -> PipelineResult:
    candidates = []
    for symbol, score in symbols_scores:
        c = Candidate(symbol=symbol, fields={})
        c.factor_score = score
        candidates.append(c)
    return PipelineResult(ranked=candidates, trace=[], top=candidates)


class TestSetAndGet:
    def test_round_trip(self, store) -> None:
        result = _result([("AAPL", 5.0), ("MSFT", 3.0)])
        store.set_latest("r1", result, now=100.0)
        snap = store.get_latest("r1")
        assert snap is not None
        assert snap.generated_at == 100.0
        assert [c.symbol for c in snap.top] == ["AAPL", "MSFT"]
        assert snap.top[0].factor_score == 5.0

    def test_unknown_ranker_is_none(self, store) -> None:
        assert store.get_latest("ghost") is None

    def test_second_set_replaces_the_first(self, store) -> None:
        store.set_latest("r1", _result([("AAPL", 1.0)]), now=1.0)
        store.set_latest("r1", _result([("MSFT", 2.0)]), now=2.0)
        snap = store.get_latest("r1")
        assert [c.symbol for c in snap.top] == ["MSFT"]
        assert snap.generated_at == 2.0

    def test_different_rankers_are_independent(self, store) -> None:
        store.set_latest("r1", _result([("AAPL", 1.0)]), now=1.0)
        store.set_latest("r2", _result([("MSFT", 1.0)]), now=1.0)
        assert [c.symbol for c in store.get_latest("r1").top] == ["AAPL"]
        assert [c.symbol for c in store.get_latest("r2").top] == ["MSFT"]

    def test_risk_flags_round_trip(self, store) -> None:
        c = Candidate(symbol="AAPL", fields={})
        c.risk_flags = ["high_pb", "rsi_overbought"]
        result = PipelineResult(ranked=[c], trace=[], top=[c])
        store.set_latest("r1", result, now=1.0)
        snap = store.get_latest("r1")
        assert snap.top[0].risk_flags == ["high_pb", "rsi_overbought"]

    def test_fields_round_trip(self, store) -> None:
        c = Candidate(symbol="AAPL", fields={"price": 190.5, "rsi": 28.4, "volume": 4200000.0})
        result = PipelineResult(ranked=[c], trace=[], top=[c])
        store.set_latest("r1", result, now=1.0)
        snap = store.get_latest("r1")
        assert snap.top[0].fields == {"price": 190.5, "rsi": 28.4, "volume": 4200000.0}

    def test_missing_fields_key_defaults_to_empty_dict(self, store) -> None:
        # Tolerates a snapshot row written before `fields` was added to the
        # persisted JSON (t.get("fields", {}) in get_latest).
        import json

        store.set_latest("r1", _result([("AAPL", 5.0)]), now=1.0)
        conn = store._get_conn()
        row = conn.execute("SELECT top_json FROM ranker_snapshots WHERE ranker_id = ?", ("r1",)).fetchone()
        top = json.loads(row["top_json"])
        del top[0]["fields"]
        conn.execute("UPDATE ranker_snapshots SET top_json = ? WHERE ranker_id = ?", (json.dumps(top), "r1"))
        conn.commit()

        snap = store.get_latest("r1")
        assert snap.top[0].fields == {}
