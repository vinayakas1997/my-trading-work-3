"""v1 A4 + A3 of the-inconsistencies-v2 (plan item 2.4c).

A4 -- `code_hash` was written to the generation store, indexed, and never
queried; the sweep side recorded params but not which code produced them, so a
generation-time discard could never be linked to a later sweep of the "same"
candidate. A base-code-mode sweep now stores the hash of the base code it
varied (same `code_hash` function), and the graveyard joins both ways.

A3 -- `param_diff_from_winner` was computed live for the HTTP response and
thrown away. Each non-winner point now stores it, so "why did this lose, how
far from the winner" is readable later.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

import pytest

from vinu_research.candidate_graveyard import query_candidate_graveyard
from vinu_research.generation_candidate_store import GenerationCandidateStore, code_hash
from vinu_research.sweep_store import SweepGridStore

BASE = "class Strat:\n    period = 9\n"


@dataclass
class _SR:
    run_id: str
    strategy_code: str = ""


@dataclass
class _Ranked:
    score: float
    risk_score: float
    complexity_score: float
    params: dict
    sweep_result: _SR


@dataclass
class _Outcome:
    params: dict
    succeeded: bool
    error: str = ""


@dataclass
class _Grid:
    requested: int
    succeeded: int
    completeness: float
    ranked: list
    pbo: dict | None
    outcomes: list
    walk_forward: dict | None = None


@dataclass
class _GenCandidate:
    code: str
    reasoning: str = ""


@dataclass
class _GenRanked:
    candidate: _GenCandidate
    score: float
    complexity_score: float


def _grid(**over) -> _Grid:
    base = dict(
        requested=4, succeeded=3, completeness=0.75, pbo=None,
        ranked=[
            _Ranked(1.5, 0.1, 0.1, {"period": 9, "mult": 2.0}, _SR("run-a", BASE.replace("9", "9"))),
            _Ranked(1.1, 0.2, 0.1, {"period": 14, "mult": 2.0}, _SR("run-b", BASE.replace("9", "14"))),
            _Ranked(0.7, 0.3, 0.1, {"period": 14, "mult": 3.5}, _SR("run-c", BASE.replace("9", "14"))),
        ],
        outcomes=[
            _Outcome({"period": 9, "mult": 2.0}, True),
            _Outcome({"period": 14, "mult": 2.0}, True),
            _Outcome({"period": 14, "mult": 3.5}, True),
            _Outcome({"period": 999, "mult": 2.0}, False, "ParameterNotFoundError: no such param"),
        ],
    )
    base.update(over)
    return _Grid(**base)


@pytest.fixture
def store():
    return SweepGridStore(":memory:")


@pytest.fixture
def gen():
    return GenerationCandidateStore(":memory:")


def _record(store, sweep_id="s1", base_code=BASE, **over):
    store.record_sweep(
        sweep_id, symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
        result=_grid(**over), now=100.0, base_code=base_code,
    )


# --------------------------------------------------------------- base_code_hash / code_hash

def test_header_stores_the_same_hash_the_generation_store_uses(store):
    _record(store)
    assert store.get_sweep("s1")["base_code_hash"] == code_hash(BASE)


def test_recipe_mode_has_no_base_code_hash(store):
    _record(store, base_code=None)
    assert store.get_sweep("s1")["base_code_hash"] is None


def test_each_succeeded_point_records_the_hash_of_the_code_it_executed(store):
    _record(store)
    pts = {p["run_id"]: p for p in store.get_sweep("s1")["points"] if p["succeeded"]}
    assert pts["run-a"]["code_hash"] == code_hash(BASE.replace("9", "9"))
    assert pts["run-b"]["code_hash"] == code_hash(BASE.replace("9", "14"))
    assert pts["run-a"]["code_hash"] != pts["run-b"]["code_hash"]


def test_failed_points_have_no_code_hash(store):
    _record(store)
    failed = [p for p in store.get_sweep("s1")["points"] if not p["succeeded"]]
    assert failed[0]["code_hash"] is None


def test_a_result_object_without_strategy_code_is_tolerated(store):
    # results written by older callers/tests only carry run_id
    class _Old:
        run_id = "old"

    ranked = [_Ranked(1.0, 0.1, 0.1, {"period": 9}, _Old())]
    _record(store, ranked=ranked, outcomes=[_Outcome({"period": 9}, True)], requested=1, succeeded=1, completeness=1.0)
    assert store.get_sweep("s1")["points"][0]["code_hash"] is None


def test_find_sweeps_by_base_code_hash(store):
    _record(store, "s1")
    _record(store, "s2", base_code="class Other:\n    x = 1\n")
    found = store.find_sweeps_by_base_code_hash(code_hash(BASE))
    assert [f["sweep_id"] for f in found] == ["s1"]
    assert store.find_sweeps_by_base_code_hash("") == []
    assert store.find_sweeps_by_base_code_hash("nope") == []


# --------------------------------------------------------------- param_diff_from_winner (A3)

def test_the_winner_has_no_diff_and_losers_store_theirs(store):
    _record(store)
    pts = {p["run_id"]: p for p in store.get_sweep("s1")["points"] if p["succeeded"]}
    assert pts["run-a"]["param_diff_from_winner"] is None  # the winner
    assert pts["run-b"]["param_diff_from_winner"] == {"period": {"candidate": 14, "winner": 9}}
    assert pts["run-c"]["param_diff_from_winner"] == {
        "period": {"candidate": 14, "winner": 9}, "mult": {"candidate": 3.5, "winner": 2.0},
    }


def test_a_failed_point_also_records_how_far_it_was_from_the_winner(store):
    _record(store)
    failed = [p for p in store.get_sweep("s1")["points"] if not p["succeeded"]][0]
    assert failed["param_diff_from_winner"] == {"period": {"candidate": 999, "winner": 9}}


def test_no_winner_means_no_diffs(store):
    _record(store, ranked=[], succeeded=0, completeness=0.0,
            outcomes=[_Outcome({"period": 999}, False, "boom")])
    pt = store.get_sweep("s1")["points"][0]
    assert pt["param_diff_from_winner"] is None


# --------------------------------------------------------------- migration of an old database

def test_an_old_v1_database_is_migrated_and_stays_readable(tmp_path):
    db = tmp_path / "old_sweep.db"
    con = sqlite3.connect(db)
    con.executescript(
        """
        CREATE TABLE sweep_runs (
            sweep_id TEXT PRIMARY KEY, symbol TEXT NOT NULL, from_date TEXT NOT NULL, to_date TEXT NOT NULL,
            requested INTEGER NOT NULL, succeeded INTEGER NOT NULL, completeness REAL NOT NULL,
            pbo_json TEXT, walk_forward_json TEXT, created_at REAL NOT NULL);
        CREATE TABLE sweep_grid_points (
            id INTEGER PRIMARY KEY AUTOINCREMENT, sweep_id TEXT NOT NULL, run_id TEXT, rank INTEGER,
            score REAL, risk_score REAL, complexity_score REAL, succeeded INTEGER NOT NULL,
            failure_reason TEXT NOT NULL DEFAULT '', params_json TEXT NOT NULL, created_at REAL NOT NULL);
        INSERT INTO sweep_runs VALUES ('legacy','MSFT','2022-01-01','2022-12-31',1,1,1.0,NULL,NULL,5.0);
        INSERT INTO sweep_grid_points (sweep_id, run_id, rank, score, succeeded, params_json, created_at)
            VALUES ('legacy','r1',1,1.0,1,'{"period": 5}',5.0);
        PRAGMA user_version=1;
        """
    )
    con.commit()
    con.close()

    s = SweepGridStore(db)
    legacy = s.get_sweep("legacy")
    assert legacy is not None and legacy["base_code_hash"] is None
    assert legacy["points"][0]["code_hash"] is None and legacy["points"][0]["param_diff_from_winner"] is None
    _record(s, "new")  # and it accepts new-style writes
    assert s.get_sweep("new")["base_code_hash"] == code_hash(BASE)


# --------------------------------------------------------------- the graveyard join (A4)

def _gen_round(gen, *, discard_code, chosen_code="class Chosen: pass", gid="gen-1"):
    gen.record_round(
        gid, symbol="AAPL", iteration=1, mode="generate",
        ranked=[
            _GenRanked(_GenCandidate(chosen_code, "winner"), 90.0, 90.0),
            _GenRanked(_GenCandidate(discard_code, "too complex"), 50.0, 50.0),
        ],
        now=1_700_000_000.0,
    )


def test_a_discarded_candidate_lists_the_sweeps_that_later_varied_it(gen, store):
    _gen_round(gen, discard_code=BASE)
    _record(store, "s1")
    entries = query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
    gen_entry = next(e for e in entries if e["source"] == "generation")
    assert [s["sweep_id"] for s in gen_entry["swept_in"]] == ["s1"]
    assert gen_entry["swept_in"][0]["requested"] == 4


def test_a_discarded_candidate_never_swept_has_an_empty_link(gen, store):
    _gen_round(gen, discard_code="class NeverSwept: pass")
    _record(store, "s1")
    gen_entry = next(e for e in query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
                     if e["source"] == "generation")
    assert gen_entry["swept_in"] == []


def test_a_failed_sweep_point_lists_the_generation_rounds_behind_its_base_code(gen, store):
    _gen_round(gen, discard_code=BASE, gid="gen-1")
    _gen_round(gen, discard_code="class X: pass", chosen_code=BASE, gid="gen-2")  # same code, chosen elsewhere
    _record(store, "s1")
    entries = query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
    sweep_entry = next(e for e in entries if e["source"] == "sweep")
    assert sweep_entry["generation_ids"] == ["gen-1", "gen-2"]
    assert sweep_entry["param_diff_from_winner"] == {"period": {"candidate": 999, "winner": 9}}


def test_recipe_mode_sweep_entries_have_no_generation_link(gen, store):
    _gen_round(gen, discard_code=BASE)
    _record(store, "s1", base_code=None)
    sweep_entry = next(e for e in query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
                       if e["source"] == "sweep")
    assert sweep_entry["generation_ids"] == []


# --------------------------------------------------------------- through run_sweep_grid itself

from unittest.mock import AsyncMock  # noqa: E402

from vinu_research.models import BacktestMetrics, BacktestResult  # noqa: E402
from vinu_research.sweep_grid import run_sweep_grid  # noqa: E402


def _bt(run_id: str, sharpe: float) -> BacktestResult:
    return BacktestResult(
        run_id=run_id, strategy_name="UserStrategy",
        metrics=BacktestMetrics(sharpe_ratio=sharpe, total_return=0.05, max_drawdown=-0.1, win_rate=0.55),
        benchmark_metrics={}, trade_count=10, equity_points=100,
        raw={"equity_points": 100, "benchmark_metrics": {}},
    )


@pytest.mark.asyncio
async def test_base_code_sweep_persists_the_hash_and_the_loser_diff_end_to_end():
    code = "class Strat:\n    fast_period = 9\n"
    tools = AsyncMock()
    tools.run_backtest.side_effect = [_bt("run-a", 2.0), _bt("run-b", 1.0)]
    store = SweepGridStore(":memory:")

    result = await run_sweep_grid(
        symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
        base_code=code, param_name="fast_period",
        param_grid=[{"fast_period": 5}, {"fast_period": 10}], tools=tools, sweep_store=store,
    )

    stored = store.get_sweep(result.sweep_id)
    assert stored["base_code_hash"] == code_hash(code)
    pts = [p for p in stored["points"] if p["succeeded"]]
    assert len(pts) == 2 and all(p["code_hash"] for p in pts)
    assert pts[0]["code_hash"] != pts[1]["code_hash"]  # the substituted code differs per point
    assert pts[0]["param_diff_from_winner"] is None  # rank 1
    assert pts[1]["param_diff_from_winner"] is not None  # the loser says how it differed
    # and the generation -> sweep join works from the same hash
    assert [s["sweep_id"] for s in store.find_sweeps_by_base_code_hash(code_hash(code))] == [result.sweep_id]


@pytest.mark.asyncio
async def test_recipe_sweep_through_run_sweep_grid_has_no_base_code_hash():
    tools = AsyncMock()
    tools.run_backtest.side_effect = [_bt("run-a", 1.0)]
    store = SweepGridStore(":memory:")
    result = await run_sweep_grid(
        symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
        recipe="crossover", param_grid=[{"fast_period": 5, "slow_period": 40}],
        tools=tools, sweep_store=store,
    )
    assert store.get_sweep(result.sweep_id)["base_code_hash"] is None


# --------------------------------------------------------------- runtime edge recording (Phase 3 extension)

@pytest.fixture
def edge_root(tmp_path, monkeypatch):
    from vinu_infra import pipeline_edge_recorder as rec

    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path))
    rec.reset_for_tests()
    yield rec
    rec.reset_for_tests()


def _edge(rec):
    return rec.resolve_edge_status_store().get_state("sweep.base_code_hash->research.graveyard")


def test_the_graveyard_join_is_recorded_empty_when_nothing_links(gen, store, edge_root):
    _gen_round(gen, discard_code="class NeverSwept: pass")
    _record(store, "s1", base_code=None)                       # recipe mode: no hash, nothing can link
    query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
    st = _edge(edge_root)
    assert st["status"] == "empty" and "0 joined" in st["last_detail"]


def test_the_graveyard_join_is_recorded_received_when_generation_and_sweep_link(gen, store, edge_root):
    _gen_round(gen, discard_code=BASE)
    _record(store, "s1")
    entries = query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
    st = _edge(edge_root)
    assert st["status"] == "received" and f"{len(entries)} entr" in st["last_detail"]


def test_recording_does_not_change_the_graveyard_result(gen, store, edge_root, monkeypatch):
    _gen_round(gen, discard_code=BASE)
    _record(store, "s1")
    with_rec = query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store)
    monkeypatch.setattr(edge_root, "resolve_edge_status_store", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert query_candidate_graveyard("AAPL", generation_store=gen, sweep_store=store) == with_rec
