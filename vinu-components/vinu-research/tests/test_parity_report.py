"""v2 A3 (the-inconsistencies-v2, Phase 5): backtest-vs-realized parity report.

Strategies: backtest Sharpe / max drawdown vs paper days (paper = the code re-run on new days, NOT real fills).
Trade plans: mean stated confidence vs realized hit rate, forecast magnitude vs realized move.
Read-only and advisory; `in_line` is only "no shortfall detectable at this sample size".
"""

from __future__ import annotations

import json
import math
import sqlite3
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from vinu_research import parity_report as pr
from vinu_research.forecast_skill import compute_brier_score, compute_directional_error
from vinu_research.models import Artifact, ArtifactStatus, CalibrationEntry
from vinu_research.server.app import create_app


def _returns(n, mean, sd, seed=1):
    rng = np.random.default_rng(seed)
    return list(rng.normal(mean, sd, n))


def _entry(direction, conf, actual, mag=0.02, artifact="a1"):
    return CalibrationEntry(
        artifact_id=artifact, forecast_direction=direction, actual_return_pct=actual, forecast_magnitude_pct=mag,
        brier_score=compute_brier_score(direction, conf, actual),
        directional_correct=compute_directional_error(direction, actual),
    )


# ------------------------------------------------------------------ realized stats

def test_realized_stats_on_known_numbers():
    s = pr.realized_stats([0.01, -0.02, 0.01, 0.0])
    assert s["n_days"] == 4 and s["hit_rate"] == 0.5
    assert s["mean_daily_return"] == pytest.approx(0.0)
    assert s["max_drawdown"] == pytest.approx(1 - (1.01 * 0.98) / 1.01)        # peak 1.01 -> trough 1.01*0.98
    assert s["sharpe"] == pytest.approx(0.0, abs=1e-12)


def test_realized_stats_is_robust_to_junk_and_empty():
    assert pr.realized_stats([])["n_days"] == 0
    s = pr.realized_stats([0.01, None, "x", float("nan"), float("inf"), 0.02])
    assert s["n_days"] == 2
    assert pr.realized_stats([0.01])["sharpe"] is None and pr.realized_stats([0.0, 0.0])["sharpe"] is None


def test_sharpe_standard_error_shrinks_with_more_days_and_matches_the_formula():
    se100, se400 = pr.sharpe_standard_error(1.0, 100), pr.sharpe_standard_error(1.0, 400)
    assert se400 == pytest.approx(se100 / 2, rel=0.02)
    sr_d = 1.0 / math.sqrt(252)
    assert se100 == pytest.approx(math.sqrt((1 + 0.5 * sr_d**2) / 100) * math.sqrt(252))
    assert pr.sharpe_standard_error(1.0, 1) is None


# ------------------------------------------------------------------ strategy parity

def test_too_few_days_is_insufficient_not_a_verdict():
    p = pr.strategy_parity("s", 1.5, -0.1, _returns(10, 0.001, 0.01))
    assert p.verdict == "insufficient_data" and "10 paper day" in p.note and p.sharpe_standard_error is None


def test_no_positive_backtest_sharpe_means_no_expectation():
    for exp in (None, 0.0, -0.4):
        assert pr.strategy_parity("s", exp, 0.1, _returns(60, 0.001, 0.01)).verdict == "no_backtest_expectation"


def test_a_strategy_that_keeps_its_edge_is_in_line():
    r = _returns(500, 0.0009, 0.007, seed=3)             # annual Sharpe ~2
    realized = pr.realized_stats(r)["sharpe"]
    p = pr.strategy_parity("s", realized * 0.9, 0.2, r)
    assert p.verdict == "in_line" and p.z_score > -pr.Z_FLAG


def test_a_strategy_whose_edge_vanished_is_flagged_underperforming():
    r = _returns(500, -0.0002, 0.01, seed=4)             # negative drift
    p = pr.strategy_parity("s", 2.0, 0.1, r)
    assert p.verdict == "underperforming" and p.z_score < -pr.Z_FLAG and p.detectable_shortfall == pytest.approx(2 * p.sharpe_standard_error)


def test_a_thin_window_says_it_is_thin():
    r = _returns(25, 0.0005, 0.01, seed=5)
    p = pr.strategy_parity("s", 1.0, 0.1, r)
    assert p.verdict == "in_line"
    assert p.detectable_shortfall > 1.0 and "weak evidence" in p.note


def test_drawdown_beyond_one_and_a_half_times_the_backtest_is_flagged_separately():
    r = [0.01] * 30 + [-0.05] * 4 + [0.01] * 30
    p = pr.strategy_parity("s", 1.0, -0.02, r)
    assert p.drawdown_exceeds_backtest is True and p.expected_max_drawdown == 0.02
    assert pr.strategy_parity("s", 1.0, -0.5, r).drawdown_exceeds_backtest is False


# ------------------------------------------------------------------ trade-plan parity

def _trades(n, conf, hit_frac, mag=0.02, hit_ret=0.02, miss_ret=-0.02, direction="long", artifact="a1"):
    hits = int(round(n * hit_frac))
    out = []
    for i in range(n):
        ret = hit_ret if i < hits else miss_ret
        out.append(_entry(direction, conf, ret if direction == "long" else -ret, mag, artifact))
    return out


def test_too_few_closed_trades_is_insufficient():
    out = pr.trade_plan_parity(_trades(10, 0.8, 0.8))
    assert out.verdict == "insufficient_data" and out.n_trades == 10


def test_overconfident_when_stated_confidence_beats_the_hit_rate():
    out = pr.trade_plan_parity(_trades(100, 0.9, 0.5))
    assert out.verdict == "overconfident" and out.hit_rate_z < -pr.Z_FLAG
    assert out.expected_hit_rate == pytest.approx(0.9) and out.realized_hit_rate == 0.5


def test_calibrated_forecasts_are_in_line():
    out = pr.trade_plan_parity(_trades(100, 0.7, 0.7, hit_ret=0.03, miss_ret=-0.01))      # mean move 0.018 vs forecast 0.02
    assert out.verdict == "in_line" and out.move_capture == pytest.approx(0.9)
    assert out.verdict == "in_line" and abs(out.hit_rate_z) < pr.Z_FLAG


def test_right_direction_but_tiny_moves_is_overstated_magnitude():
    out = pr.trade_plan_parity(_trades(100, 0.7, 0.7, mag=0.05, hit_ret=0.004, miss_ret=-0.001))
    assert out.verdict == "overstated_magnitude" and out.move_capture < 0.5


def test_short_calls_are_measured_in_their_own_direction():
    out = pr.trade_plan_parity(_trades(60, 0.7, 0.7, direction="short"))
    assert out.realized_hit_rate == pytest.approx(0.7) and out.move_capture > 0


def test_neutral_and_junk_entries_are_ignored():
    neutral = CalibrationEntry("a", "neutral", 0.01, brier_score=0.25)
    out = pr.trade_plan_parity(_trades(40, 0.7, 0.7) + [neutral, object(), None])
    assert out.n_trades == 40


# ------------------------------------------------------------------ the report and the db reader

def test_build_report_counts_verdicts_and_carries_the_caveat():
    strat = lambda i, sh: SimpleNamespace(artifact_id=i, initial_sharpe=sh, initial_max_dd=-0.1)  # noqa: E731
    rep = pr.build_parity_report(
        [strat("a", 1.0), strat("b", 1.0), strat("c", 0.0)],
        {"a": _returns(300, 0.0009, 0.007, seed=8), "b": _returns(5, 0.0, 0.01)},
        _trades(40, 0.7, 0.7),
    )
    assert rep["strategies"]["count"] == 3
    assert rep["strategies"]["by_verdict"]["insufficient_data"] == 2          # b: 5 days; c: no paper series at all
    assert "not real fills" in rep["caveat"] and "execution parity" in rep["caveat"]
    assert rep["trade_plans"]["n_trades"] == 40


def test_read_paper_returns_db_round_trip_and_failure_modes(tmp_path):
    assert pr.read_paper_returns_db(None) is None and pr.read_paper_returns_db(tmp_path) is None   # no file
    db = tmp_path / "paper_performance.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE paper_performance (artifact_id TEXT PRIMARY KEY, returns_json TEXT, updated_at REAL, meta_json TEXT)")
    conn.execute("INSERT INTO paper_performance VALUES ('a', ?, 0, '{}')", (json.dumps([0.01, "x", 0.02]),))
    conn.execute("INSERT INTO paper_performance VALUES ('b', 'not json', 0, '{}')")
    conn.commit()
    conn.close()
    assert pr.read_paper_returns_db(tmp_path) == {"a": [0.01, 0.02]}
    (tmp_path / "bad").mkdir()
    (tmp_path / "bad" / "paper_performance.db").write_bytes(b"not sqlite")
    assert pr.read_paper_returns_db(tmp_path / "bad") is None


# ------------------------------------------------------------------ the route

@pytest.fixture
def client(service):
    app = create_app(service)
    with TestClient(app) as c:
        yield c


def _seed(service, sharpe=1.5):
    store = service.strategy_store
    store.upsert_artifact(Artifact(artifact_id="strat1", type="strategy", name="s", universe=["AAPL"],
                                   status=ArtifactStatus.BENCHING, initial_sharpe=sharpe, initial_max_dd=-0.1))
    store.upsert_artifact(Artifact(artifact_id="plan1", type="trade_plan", name="p", universe=["AAPL"]))
    for e in _trades(40, 0.7, 0.7, artifact="plan1"):
        store.append_calibration_entry(e)


def test_route_joins_strategies_paper_days_and_trade_plans(client, service, monkeypatch):
    _seed(service)
    monkeypatch.setattr(pr, "read_paper_returns_db", lambda root: {"strat1": _returns(300, 0.0009, 0.007, seed=9)})
    body = client.get("/research/parity-report").json()
    assert body["paper_source"] == "db" and body["kind"] == "backtest_vs_paper_replay"
    (row,) = body["strategies"]["rows"]
    assert row["artifact_id"] == "strat1" and row["verdict"] in ("in_line", "underperforming") and row["realized"]["n_days"] == 300
    assert body["trade_plans"]["n_trades"] == 40 and "not real fills" in body["caveat"]


def test_route_thresholds_are_parameters(client, service, monkeypatch):
    _seed(service)
    monkeypatch.setattr(pr, "read_paper_returns_db", lambda root: {"strat1": _returns(30, 0.001, 0.01)})
    strict = client.get("/research/parity-report?min_days=100&min_trades=100").json()
    assert strict["strategies"]["rows"][0]["verdict"] == "insufficient_data" and strict["trade_plans"]["verdict"] == "insufficient_data"
    loose = client.get("/research/parity-report?min_days=10&min_trades=10").json()
    assert loose["strategies"]["rows"][0]["verdict"] != "insufficient_data" and loose["trade_plans"]["verdict"] != "insufficient_data"


def test_route_without_paper_data_reports_it_and_does_not_fail(client, service, monkeypatch):
    _seed(service)
    monkeypatch.setattr(pr, "read_paper_returns_db", lambda root: None)       # no mount; the agent API is unreachable in tests
    body = client.get("/research/parity-report").json()
    assert body["paper_source"] in ("agent_api", "unavailable")
    assert body["strategies"]["rows"][0]["verdict"] == "insufficient_data"
    assert body["trade_plans"]["n_trades"] == 40


def test_route_on_an_empty_system_is_a_clean_empty_report(client):
    body = client.get("/research/parity-report").json()
    assert body["strategies"] == {"count": 0, "by_verdict": {}, "rows": []}
    assert body["trade_plans"]["verdict"] == "insufficient_data"
