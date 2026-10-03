"""v1 C4 of the-inconsistencies-v2 (plan item 2.4d), strategy half.

A degraded strategy run (symbols missing required upstream data, or weights
clamped / zeroed by the sanity gate) was visible only in that one call's
response and a log line. The facts are now persisted on the run row and
returned by GET /strategy/runs. Also fixes `log_run`, which stored
`str(metadata)` -- a Python repr nothing could parse back.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.models.strategy import StrategyConfig
from vinu_strategy.service import StrategyService
from vinu_strategy.storage.meta import MetaStorage


@pytest.fixture
def meta(tmp_path):
    m = MetaStorage(tmp_path / "meta.db")
    yield m
    m.close()


# ------------------------------------------------------------------ storage

def test_metadata_round_trips_as_json(meta):
    meta.log_run("s", "run-1", symbol="AAPL", metadata={"is_degraded": True, "degraded_symbols": ["AAPL"]})
    run = meta.get_runs("s")[0]
    assert run["metadata"] == {"is_degraded": True, "degraded_symbols": ["AAPL"]}
    assert run["run_id"] == "run-1" and run["status"] == "completed"  # existing fields unchanged


def test_no_metadata_reads_back_as_an_empty_dict(meta):
    meta.log_run("s", "run-1")
    assert meta.get_runs("s")[0]["metadata"] == {}


def test_runs_written_before_the_fix_as_a_python_repr_are_still_readable(meta):
    conn = meta._get_conn()
    conn.execute(
        "INSERT INTO strategy_runs (strategy_name, run_id, symbol, timestamp, status, metadata) "
        "VALUES ('s', 'legacy', 'AAPL', '2026-09-01T00:00:00', 'completed', ?)",
        (str({"symbols": ["AAPL"], "count": 1}),),  # what the old str(metadata) wrote
    )
    conn.commit()
    assert meta.get_runs("s")[0]["metadata"] == {"symbols": ["AAPL"], "count": 1}


@pytest.mark.parametrize("junk", ["not json at all", "[1, 2, 3]", "", None, "{'unterminated': "])
def test_unreadable_metadata_is_an_empty_dict_never_an_error(meta, junk):
    conn = meta._get_conn()
    conn.execute(
        "INSERT INTO strategy_runs (strategy_name, run_id, symbol, timestamp, status, metadata) "
        "VALUES ('s', 'junk', 'AAPL', '2026-09-01T00:00:00', 'completed', ?)",
        (junk,),
    )
    conn.commit()
    assert meta.get_runs("s")[0]["metadata"] == {}


def test_get_runs_without_a_name_also_carries_metadata(meta):
    meta.log_run("a", "r1", metadata={"is_degraded": False})
    meta.log_run("b", "r2", metadata={"is_degraded": True})
    by_id = {r["run_id"]: r for r in meta.get_runs()}
    assert by_id["r1"]["metadata"]["is_degraded"] is False and by_id["r2"]["metadata"]["is_degraded"] is True


# ------------------------------------------------------------------ service persists the facts

def _cfg(**overrides) -> StrategyConfig:
    return StrategyConfig(name="s", description="", schedule="daily", **overrides)


def _service(config, pipeline_meta=None) -> StrategyService:
    svc = StrategyService.__new__(StrategyService)
    svc._config = VinuStrategyConfig(
        host="127.0.0.1", port=8084, data_root=None, strategies_dir=None,
        features_api_url="", correlation_api_url="",
        max_weight=0.25, cash_floor=0.10, rebalance_freq="daily", shared_watchlist_path=None,
    )
    svc._registry = MagicMock()
    svc._registry.get.return_value = config
    svc._features_client = MagicMock()
    svc._features_client.get_features.return_value = {}
    svc._weight_storage = MagicMock()
    svc._meta_storage = MagicMock()
    svc._pipeline = MagicMock()
    svc._pipeline.run.return_value = ({"AAPL": 0.0, "MSFT": 0.0}, pipeline_meta or {"rule_trace": {}})
    return svc


def _logged_metadata(svc: StrategyService) -> dict:
    return svc._meta_storage.log_run.call_args.kwargs["metadata"]


def test_a_degraded_run_persists_which_symbols_were_missing_data():
    svc = _service(_cfg(features_required=["rsi_14"]))  # features fetch returns {} -> degraded
    svc.evaluate("s", symbols=["AAPL", "MSFT"])
    md = _logged_metadata(svc)
    assert md["is_degraded"] is True
    assert md["degraded_symbols"] == ["AAPL", "MSFT"]
    assert md["sanity_issue_count"] == 0


def test_a_clean_run_persists_is_degraded_false():
    svc = _service(_cfg())  # nothing required -> nothing can be missing
    svc.evaluate("s", symbols=["AAPL"])
    assert _logged_metadata(svc) == {"is_degraded": False, "degraded_symbols": [], "sanity_issue_count": 0}


def test_sanity_issues_from_the_pipeline_are_counted():
    svc = _service(_cfg(), pipeline_meta={"rule_trace": {}, "sanity_issues": {"AAPL": "nan weight", "MSFT": "inf weight"}})
    svc.evaluate("s", symbols=["AAPL", "MSFT"])
    assert _logged_metadata(svc)["sanity_issue_count"] == 2


def test_the_symbol_list_is_bounded():
    symbols = [f"S{i:03d}" for i in range(50)]
    svc = _service(_cfg(features_required=["rsi_14"]))
    svc._pipeline.run.return_value = ({s: 0.0 for s in symbols}, {"rule_trace": {}})
    svc.evaluate("s", symbols=symbols)
    assert len(_logged_metadata(svc)["degraded_symbols"]) == 20


# ------------------------------------------------------------------ runtime edge recording (Phase 3 extension)

@pytest.fixture
def edge_root(tmp_path, monkeypatch):
    from vinu_infra import pipeline_edge_recorder as rec

    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield rec
    rec.reset_for_tests()


def test_each_run_records_the_run_quality_edge_with_its_facts(edge_root):
    svc = _service(_cfg(features_required=["rsi_14"]))
    svc.evaluate("s", symbols=["AAPL", "MSFT"])
    st = edge_root.resolve_edge_status_store().get_state("strategy.run_quality->strategy.runs_api")
    assert st["status"] == "received" and "degraded=True" in st["last_detail"] and "s:" in st["last_detail"]
    svc2 = _service(_cfg())
    svc2.evaluate("s", symbols=["AAPL"])
    st = edge_root.resolve_edge_status_store().get_state("strategy.run_quality->strategy.runs_api")
    assert "degraded=False" in st["last_detail"] and st["n_received"] == 2


def test_a_broken_recorder_does_not_change_the_persisted_metadata(edge_root, monkeypatch):
    monkeypatch.setattr(edge_root, "resolve_edge_status_store", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    svc = _service(_cfg())
    svc.evaluate("s", symbols=["AAPL"])
    assert _logged_metadata(svc) == {"is_degraded": False, "degraded_symbols": [], "sanity_issue_count": 0}
