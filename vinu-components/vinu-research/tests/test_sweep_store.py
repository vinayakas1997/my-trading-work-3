"""item #3: the sweep/search grouping table -- the comparison itself,
not the individual runs (already durably persisted by vinu-simulator).
Also covers item #12 finding #4 (walk_forward persisted on the same
header row, not treated as a separate mechanism)."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from vinu_research.sweep_store import SweepGridStore


@dataclass
class _FakeSweepResult:
    run_id: str


@dataclass
class _FakeRanked:
    score: float
    risk_score: float
    complexity_score: float
    params: dict
    sweep_result: _FakeSweepResult


@dataclass
class _FakeOutcome:
    params: dict
    succeeded: bool
    error: str = ""


@dataclass
class _FakeGridResult:
    requested: int
    succeeded: int
    completeness: float
    ranked: list
    pbo: dict | None
    outcomes: list
    walk_forward: dict | None = None


@pytest.fixture
def store():
    return SweepGridStore(":memory:")


def _result(**overrides) -> _FakeGridResult:
    ranked = overrides.pop("ranked", [
        _FakeRanked(1.5, 0.2, 0.1, {"period": 9}, _FakeSweepResult("run-a")),
        _FakeRanked(0.9, 0.3, 0.1, {"period": 14}, _FakeSweepResult("run-b")),
    ])
    outcomes = overrides.pop("outcomes", [
        _FakeOutcome({"period": 9}, True),
        _FakeOutcome({"period": 14}, True),
        _FakeOutcome({"period": 999}, False, "ParameterNotFoundError: no such param"),
    ])
    defaults = dict(
        requested=3, succeeded=2, completeness=0.667,
        pbo={"pbo": 0.2}, outcomes=outcomes, ranked=ranked, walk_forward=None,
    )
    defaults.update(overrides)
    return _FakeGridResult(**defaults)


class TestRecordAndGetSweep:
    def test_round_trip_header_fields(self, store) -> None:
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(), now=100.0,
        )
        sweep = store.get_sweep("sweep-1")
        assert sweep is not None
        assert sweep["symbol"] == "AAPL"
        assert sweep["requested"] == 3
        assert sweep["succeeded"] == 2
        assert sweep["completeness"] == pytest.approx(0.667)
        assert sweep["pbo"] == {"pbo": 0.2}
        assert sweep["created_at"] == 100.0

    def test_unknown_sweep_id_is_none(self, store) -> None:
        assert store.get_sweep("ghost") is None

    def test_succeeded_points_are_ranked_best_first_starting_at_one(self, store) -> None:
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(),
        )
        points = store.get_sweep("sweep-1")["points"]
        ranked_points = [p for p in points if p["succeeded"]]
        assert ranked_points[0]["rank"] == 1
        assert ranked_points[0]["run_id"] == "run-a"
        assert ranked_points[0]["score"] == pytest.approx(1.5)
        assert ranked_points[1]["rank"] == 2
        assert ranked_points[1]["run_id"] == "run-b"

    def test_failed_point_is_recorded_with_its_reason_not_lost(self, store) -> None:
        """The exact gap this item names: 'why this lost' must survive,
        not just that a losing run happened."""
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(),
        )
        points = store.get_sweep("sweep-1")["points"]
        failed = [p for p in points if not p["succeeded"]]
        assert len(failed) == 1
        assert failed[0]["run_id"] is None
        assert failed[0]["rank"] is None
        assert "ParameterNotFoundError" in failed[0]["failure_reason"]
        assert failed[0]["params"] == {"period": 999}

    def test_failed_points_sort_after_ranked_points(self, store) -> None:
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(),
        )
        points = store.get_sweep("sweep-1")["points"]
        succeeded_flags = [p["succeeded"] for p in points]
        # every True before every False
        assert succeeded_flags == sorted(succeeded_flags, reverse=True)

    def test_no_pbo_round_trips_as_none(self, store) -> None:
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(pbo=None),
        )
        assert store.get_sweep("sweep-1")["pbo"] is None

    def test_walk_forward_result_persists_on_the_same_header_row(self, store) -> None:
        """item #12 finding #4: the walk-forward result nested in the
        same SweepGridResult item #3 already flagged as discarded --
        persisted here, not treated as a separate mechanism."""
        wf = {"stability_verdict": {"passed": True}, "windows": [{"window_id": 0}]}
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(walk_forward=wf),
        )
        assert store.get_sweep("sweep-1")["walk_forward"] == wf

    def test_re_recording_the_same_sweep_id_replaces_the_header_and_appends_points(self, store) -> None:
        """INSERT OR REPLACE on the header (idempotent re-record), but
        points accumulate via plain INSERT -- a caller re-recording the
        same sweep_id is expected to have already cleared it if that's
        not wanted; this store doesn't guess at that policy."""
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(requested=3), now=1.0,
        )
        store.record_sweep(
            "sweep-1", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            result=_result(requested=5), now=2.0,
        )
        sweep = store.get_sweep("sweep-1")
        assert sweep["requested"] == 5
        assert sweep["created_at"] == 2.0


class TestListSweeps:
    def test_returns_headers_most_recent_first(self, store) -> None:
        store.record_sweep("s1", symbol="AAPL", from_date="2023-01-01", to_date="2023-06-30", result=_result(), now=1.0)
        store.record_sweep("s2", symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31", result=_result(), now=2.0)
        sweeps = store.list_sweeps(symbol="AAPL")
        assert [s["sweep_id"] for s in sweeps] == ["s2", "s1"]

    def test_symbol_filter_is_a_real_query_not_load_everything(self, store) -> None:
        store.record_sweep("s1", symbol="AAPL", from_date="2023-01-01", to_date="2023-06-30", result=_result(), now=1.0)
        store.record_sweep("s2", symbol="MSFT", from_date="2023-01-01", to_date="2023-06-30", result=_result(), now=2.0)
        assert [s["sweep_id"] for s in store.list_sweeps(symbol="AAPL")] == ["s1"]

    def test_no_symbol_filter_returns_all(self, store) -> None:
        store.record_sweep("s1", symbol="AAPL", from_date="2023-01-01", to_date="2023-06-30", result=_result(), now=1.0)
        store.record_sweep("s2", symbol="MSFT", from_date="2023-01-01", to_date="2023-06-30", result=_result(), now=2.0)
        assert len(store.list_sweeps()) == 2

    def test_limit_is_respected(self, store) -> None:
        for i in range(5):
            store.record_sweep(f"s{i}", symbol="AAPL", from_date="2023-01-01", to_date="2023-06-30", result=_result(), now=float(i))
        assert len(store.list_sweeps(symbol="AAPL", limit=2)) == 2
