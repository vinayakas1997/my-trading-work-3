from __future__ import annotations

import pytest

from vinu_screener.pipeline.candidate import Candidate
from vinu_screener.pipeline.pipeline import PipelineResult
from vinu_screener.rankers.churn import ChurnEvent, RankerChurnStore, diff_rankings, record_ranking
from vinu_screener.rankers.snapshot_store import RankedSnapshotStore


class TestDiffRankings:
    def test_no_previous_ranking_produces_no_events(self) -> None:
        assert diff_rankings("r1", None, ["AAPL", "MSFT"], now=100.0) == []

    def test_identical_rankings_produce_no_events(self) -> None:
        assert diff_rankings("r1", ["AAPL", "MSFT"], ["AAPL", "MSFT"], now=100.0) == []

    def test_new_symbol_is_an_entered_event(self) -> None:
        events = diff_rankings("r1", ["AAPL"], ["AAPL", "MSFT"], now=100.0)
        assert len(events) == 1
        assert events[0].symbol == "MSFT"
        assert events[0].kind == "entered"
        assert events[0].to_rank == 2
        assert events[0].from_rank is None

    def test_dropped_symbol_is_an_exited_event(self) -> None:
        events = diff_rankings("r1", ["AAPL", "MSFT"], ["AAPL"], now=100.0)
        assert len(events) == 1
        assert events[0].symbol == "MSFT"
        assert events[0].kind == "exited"
        assert events[0].from_rank == 2
        assert events[0].to_rank is None

    def test_symbol_can_both_exit_and_a_different_one_enter_in_the_same_diff(self) -> None:
        events = diff_rankings("r1", ["AAPL", "MSFT"], ["AAPL", "GOOG"], now=100.0)
        kinds = {(e.symbol, e.kind) for e in events}
        assert kinds == {("MSFT", "exited"), ("GOOG", "entered")}

    def test_rank_position_shifting_without_membership_change_is_not_churn(self) -> None:
        # MSFT moved from #2 to #1 and AAPL from #1 to #2 -- same membership,
        # no entered/exited events, even though order changed.
        events = diff_rankings("r1", ["AAPL", "MSFT"], ["MSFT", "AAPL"], now=100.0)
        assert events == []

    def test_events_carry_the_ranker_id_and_timestamp(self) -> None:
        events = diff_rankings("myranker", ["AAPL"], ["AAPL", "MSFT"], now=42.0)
        assert events[0].ranker_id == "myranker"
        assert events[0].at == 42.0

    def test_empty_to_empty_is_no_events(self) -> None:
        assert diff_rankings("r1", [], [], now=1.0) == []

    def test_everything_exits_when_new_ranking_is_empty(self) -> None:
        events = diff_rankings("r1", ["AAPL", "MSFT"], [], now=1.0)
        assert {e.symbol for e in events} == {"AAPL", "MSFT"}
        assert all(e.kind == "exited" for e in events)


class TestRankerChurnStore:
    @pytest.fixture
    def store(self):
        return RankerChurnStore(":memory:")

    def test_record_then_history_round_trip(self, store) -> None:
        events = [ChurnEvent("r1", "AAPL", "entered", 100.0, to_rank=3)]
        store.record(events)
        history = store.history("r1")
        assert len(history) == 1
        assert history[0].symbol == "AAPL"
        assert history[0].to_rank == 3

    def test_record_empty_list_is_a_noop(self, store) -> None:
        store.record([])
        assert store.history("r1") == []

    def test_history_is_most_recent_first(self, store) -> None:
        store.record([ChurnEvent("r1", "AAPL", "entered", 1.0)])
        store.record([ChurnEvent("r1", "AAPL", "exited", 2.0)])
        history = store.history("r1")
        assert [h.at for h in history] == [2.0, 1.0]

    def test_history_filters_by_ranker(self, store) -> None:
        store.record([ChurnEvent("r1", "AAPL", "entered", 1.0)])
        store.record([ChurnEvent("r2", "MSFT", "entered", 1.0)])
        assert [h.symbol for h in store.history("r1")] == ["AAPL"]

    def test_history_filters_by_symbol(self, store) -> None:
        store.record([ChurnEvent("r1", "AAPL", "entered", 1.0), ChurnEvent("r1", "MSFT", "entered", 1.0)])
        assert [h.symbol for h in store.history("r1", symbol="AAPL")] == ["AAPL"]

    def test_history_limit_caps_results(self, store) -> None:
        for i in range(5):
            store.record([ChurnEvent("r1", "AAPL", "entered", float(i))])
        assert len(store.history("r1", limit=2)) == 2

    def test_unknown_ranker_history_is_empty(self, store) -> None:
        assert store.history("ghost") == []


def _result(symbols: list[str]) -> PipelineResult:
    candidates = [Candidate(symbol=s, fields={}) for s in symbols]
    return PipelineResult(ranked=candidates, trace=[], top=candidates)


class TestRecordRanking:
    @pytest.fixture
    def snapshots(self):
        return RankedSnapshotStore(":memory:")

    @pytest.fixture
    def churn(self):
        return RankerChurnStore(":memory:")

    def test_first_run_persists_but_produces_no_churn(self, snapshots, churn) -> None:
        snapshot, events = record_ranking(snapshots, churn, "r1", _result(["AAPL", "MSFT"]), now=1.0)
        assert [c.symbol for c in snapshot.top] == ["AAPL", "MSFT"]
        assert events == []
        assert churn.history("r1") == []

    def test_second_run_diffs_against_the_first(self, snapshots, churn) -> None:
        record_ranking(snapshots, churn, "r1", _result(["AAPL", "MSFT"]), now=1.0)
        snapshot, events = record_ranking(snapshots, churn, "r1", _result(["AAPL", "GOOG"]), now=2.0)
        assert {(e.symbol, e.kind) for e in events} == {("MSFT", "exited"), ("GOOG", "entered")}
        assert [c.symbol for c in snapshot.top] == ["AAPL", "GOOG"]

    def test_events_are_persisted_to_the_churn_store(self, snapshots, churn) -> None:
        record_ranking(snapshots, churn, "r1", _result(["AAPL"]), now=1.0)
        record_ranking(snapshots, churn, "r1", _result(["MSFT"]), now=2.0)
        history = churn.history("r1")
        assert {(h.symbol, h.kind) for h in history} == {("AAPL", "exited"), ("MSFT", "entered")}

    def test_works_with_no_churn_store(self, snapshots) -> None:
        record_ranking(snapshots, None, "r1", _result(["AAPL"]), now=1.0)
        snapshot, events = record_ranking(snapshots, None, "r1", _result(["MSFT"]), now=2.0)
        assert {(e.symbol, e.kind) for e in events} == {("AAPL", "exited"), ("MSFT", "entered")}

    def test_three_consecutive_runs_each_diff_against_the_immediately_prior_one(self, snapshots, churn) -> None:
        record_ranking(snapshots, churn, "r1", _result(["A", "B"]), now=1.0)
        record_ranking(snapshots, churn, "r1", _result(["A", "C"]), now=2.0)  # B exits, C enters
        record_ranking(snapshots, churn, "r1", _result(["A", "B"]), now=3.0)  # C exits, B re-enters
        history = churn.history("r1")
        assert len(history) == 4
        assert {(h.symbol, h.kind, h.at) for h in history} == {
            ("B", "exited", 2.0), ("C", "entered", 2.0),
            ("C", "exited", 3.0), ("B", "entered", 3.0),
        }
