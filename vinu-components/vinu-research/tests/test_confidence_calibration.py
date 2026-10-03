"""logic-audit B1 (the-inconsistencies-v2, Phase 4): the forecast LLM's stated confidence is used raw as
P(win) in the Trade Score's EV term and as a confluence vote. This learns a reliability map from closed trades
and (opt-in) uses the calibrated number; the confluence vote can be dropped (opt-in).

Pure map + gate parameters + the real author_trade_plan path against a seeded strategy_store.db.
"""

from __future__ import annotations

import math

import pandas as pd
import pytest

from vinu_research import confidence_calibration as cc
from vinu_research.config import ResearchConfig, TradeScoreThresholds
from vinu_research.forecast_skill import compute_brier_score, compute_directional_error
from vinu_research.gates.trade_score_gate import compute_trade_score
from vinu_research.models import Artifact, CalibrationEntry, Forecast, RiskBand, SignalEntry
from vinu_research.storage.strategy_store import SqliteStrategyStore
from vinu_research.trade_plan_authoring import author_trade_plan

pytestmark = pytest.mark.asyncio


def _entry(direction, conf, actual_ret, artifact="a1") -> CalibrationEntry:
    """Built exactly the way CalibrationTracker.add_entry builds one."""
    return CalibrationEntry(
        artifact_id=artifact, forecast_direction=direction, actual_return_pct=actual_ret, forecast_magnitude_pct=0.02,
        brier_score=compute_brier_score(direction, conf, actual_ret),
        directional_correct=compute_directional_error(direction, actual_ret),
    )


# ------------------------------------------------------------------ recovering the stated confidence

@pytest.mark.parametrize("direction,actual", [("long", 0.03), ("long", -0.03), ("short", -0.02), ("short", 0.02)])
@pytest.mark.parametrize("conf", [0.55, 0.7, 0.8, 0.95])
async def test_recover_pairs_round_trips_the_stated_confidence(direction, actual, conf):
    (c, hit), = cc.recover_pairs([_entry(direction, conf, actual)])
    assert c == pytest.approx(conf, abs=1e-9)
    assert hit == compute_directional_error(direction, actual)


async def test_neutral_and_corrupt_entries_are_skipped():
    neutral = CalibrationEntry("a", "neutral", 0.01, brier_score=0.25, directional_correct=False)
    corrupt_hi = CalibrationEntry("a", "long", 0.01, brier_score=4.0, directional_correct=True)
    corrupt_nan = CalibrationEntry("a", "long", 0.01, brier_score=math.nan, directional_correct=True)
    assert cc.recover_pairs([neutral, corrupt_hi, corrupt_nan, object()]) == []


# ------------------------------------------------------------------ the map

async def test_buckets_count_hits_and_the_top_edge_belongs_to_the_last_bucket():
    m = cc.build_reliability_map([(0.85, True), (0.85, False), (0.81, True), (1.0, True), (0.05, False)], min_samples=2)
    by_lo = {round(b.lo, 1): b for b in m.buckets}
    assert (by_lo[0.8].n, by_lo[0.8].hits) == (3, 2)
    assert (by_lo[0.9].n, by_lo[0.9].hits) == (1, 1)            # 1.0 lands in [0.9, 1.0]
    assert (by_lo[0.0].n, by_lo[0.0].hits) == (1, 0)
    assert m.n_pairs == 5 and len(m.buckets) == 10


async def test_bad_bucket_width_is_rejected():
    for w in (0.0, -0.1, 1.5):
        with pytest.raises(ValueError):
            cc.build_reliability_map([], bucket_width=w)


# ------------------------------------------------------------------ calibrate()

def _map(conf, hits, n, min_samples=30):
    return cc.build_reliability_map([(conf, i < hits) for i in range(n)], min_samples=min_samples)


async def test_no_map_or_empty_map_returns_raw():
    assert cc.calibrate(0.8, None).source == "raw_no_map" and cc.calibrate(0.8, None).calibrated == 0.8
    assert cc.calibrate(0.8, cc.ReliabilityMap()).source == "raw_no_map"


async def test_below_the_sample_floor_returns_raw_not_a_guess():
    out = cc.calibrate(0.9, _map(0.9, hits=1, n=29))             # terrible record, but only 29 trades
    assert out.source == "raw_insufficient_sample" and out.calibrated == 0.9 and out.n_bucket == 29


async def test_an_overconfident_bucket_is_pulled_down_with_shrinkage():
    out = cc.calibrate(0.9, _map(0.9, hits=50, n=100))           # states 0.9, hits 50%
    assert out.source == "calibrated" and out.bucket_hit_rate == 0.5
    assert out.calibrated == pytest.approx((50 + 30 * 0.9) / (100 + 30))   # shrunk toward raw by min_samples pseudo-trades
    assert 0.5 < out.calibrated < 0.9


async def test_an_underconfident_bucket_is_pulled_up():
    assert cc.calibrate(0.6, _map(0.6, hits=90, n=100)).calibrated > 0.6


async def test_a_well_calibrated_bucket_barely_moves():
    out = cc.calibrate(0.7, _map(0.7, hits=70, n=100))
    assert out.calibrated == pytest.approx(0.7, abs=1e-9)


@pytest.mark.parametrize("raw", [-0.1, 1.2, math.nan, "x", None])
async def test_invalid_input_is_returned_untouched_and_never_raises(raw):
    out = cc.calibrate(raw, _map(0.7, 70, 100))
    assert out.source == "raw_invalid"


async def test_describe_names_the_evidence():
    assert "realized hit-rate=0.50" in cc.calibrate(0.9, _map(0.9, 50, 100)).describe()
    assert "raw_insufficient_sample" in cc.calibrate(0.9, _map(0.9, 1, 3)).describe()


# ------------------------------------------------------------------ the gate parameters

def _forecast(conf=0.9, signals=()):
    return Forecast(direction="long", confidence=conf, magnitude_pct=0.04, magnitude_std=0.01, horizon_days=3,
                    signals=list(signals))


_RB = RiskBand(expected_drawdown=0.03, cvar_95_limit=0.04, max_position_size_pct=0.1)


async def test_ev_confidence_replaces_the_raw_one_in_the_ev_term_only():
    f = _forecast(0.9)
    raw = compute_trade_score(f, _RB, None)
    low = compute_trade_score(f, _RB, None, ev_confidence=0.55)
    assert low.ev_score < raw.ev_score
    assert (low.confluence_score, low.risk_score) == (raw.confluence_score, raw.risk_score)
    assert compute_trade_score(f, _RB, None, ev_confidence=None).ev_score == raw.ev_score


async def test_excluding_forecast_confidence_removes_that_vote_from_the_confluence():
    sigs = [SignalEntry("forecast_confidence", "supporting", 0.9, "forecast_skill"),
            SignalEntry("regime", "contradicting", 0.6, "regime")]
    f = _forecast(0.9, sigs)
    with_vote = compute_trade_score(f, _RB, None)
    without = compute_trade_score(f, _RB, None, confluence_exclude_signals=frozenset({"forecast_confidence"}))
    assert without.confluence_score < with_vote.confluence_score       # only the contradicting vote is left
    only_conf = _forecast(0.9, sigs[:1])
    neutral = compute_trade_score(only_conf, _RB, None, confluence_exclude_signals=frozenset({"forecast_confidence"}))
    assert neutral.confluence_score == TradeScoreThresholds().confluence_max / 2.0   # nothing left -> neutral, as before


# ------------------------------------------------------------------ through author_trade_plan

class _Tools:
    async def get_benchmark_data(self, symbol, from_date, to_date):
        return pd.Series(([0.01] * 65 + [-0.005] * 35))

    async def get_angle_rows(self, angle_name, symbol):
        return []

    async def get_options_snapshot(self, symbol):
        return None

    async def get_latest_debate_run(self, preset_name, symbol):
        return None

    async def fetch_screener_rank_percentile(self, ranker_id, symbol):
        return None


class _Llm:
    def __init__(self, conf=0.9):
        self.conf = conf

    async def chat_json(self, system, user, *, raise_on_failure=False):
        return {"direction": "long", "confidence": self.conf, "magnitude_pct": 0.03,
                "magnitude_std": 0.01, "horizon_days": 3, "reasoning": "x"}


def _seed(tmp_path, conf=0.9, hits=50, n=100):
    """n closed 'long at stated conf' trades, `hits` of them right."""
    store = SqliteStrategyStore(tmp_path / "strategy_store.db")
    store.upsert_artifact(Artifact(artifact_id="a1", type="trade_plan", name="a1", universe=["AAPL"]))
    for i in range(n):
        store.append_calibration_entry(_entry("long", conf, 0.02 if i < hits else -0.02))
    return store


def _conf_line(plan):
    lines = [r for r in plan.trade_score.reasons if r.startswith("calibrated_confidence=")]
    return lines[0] if lines else None


async def test_flags_default_to_log_on_use_off():
    c = ResearchConfig()
    assert (c.confidence_reliability_log_enabled, c.calibrated_confidence_in_ev_enabled,
            c.confluence_excludes_forecast_confidence) == (True, False, False)
    assert c.confidence_calibration_min_samples == 30


async def test_env_flags_are_read(monkeypatch):
    monkeypatch.setenv("VINU_RESEARCH_CALIBRATED_CONFIDENCE_IN_EV_ENABLED", "true")
    monkeypatch.setenv("VINU_RESEARCH_CONFLUENCE_EXCLUDES_FORECAST_CONFIDENCE", "1")
    monkeypatch.setenv("VINU_RESEARCH_CONFIDENCE_RELIABILITY_LOG_ENABLED", "false")
    monkeypatch.setenv("VINU_RESEARCH_CONFIDENCE_CALIBRATION_MIN_SAMPLES", "12")
    from vinu_research.config import ResearchConfig as RC
    c = RC.from_env() if hasattr(RC, "from_env") else None
    if c is None:
        from vinu_research.config import load_config
        c = load_config()
    assert c.calibrated_confidence_in_ev_enabled and c.confluence_excludes_forecast_confidence
    assert c.confidence_reliability_log_enabled is False and c.confidence_calibration_min_samples == 12


async def test_log_only_writes_the_evidence_line_and_leaves_the_score_alone(tmp_path):
    _seed(tmp_path)                                                    # states 0.9, hits 50%
    plan_log = await author_trade_plan("AAPL", "daily", ResearchConfig(data_root=tmp_path), _Tools(), _Llm(0.9))
    plan_off = await author_trade_plan(
        "AAPL", "daily", ResearchConfig(data_root=tmp_path, confidence_reliability_log_enabled=False), _Tools(), _Llm(0.9))
    line = _conf_line(plan_log)
    assert line and "raw=0.90" in line and "realized hit-rate=0.50" in line and "log-only, EV uses raw" in line
    assert _conf_line(plan_off) is None
    assert plan_log.trade_score.ev_score == plan_off.trade_score.ev_score
    assert plan_log.trade_score.total_score == plan_off.trade_score.total_score


async def test_in_ev_uses_the_calibrated_number_and_lowers_an_overconfident_score(tmp_path):
    _seed(tmp_path)
    raw = await author_trade_plan("AAPL", "daily", ResearchConfig(data_root=tmp_path), _Tools(), _Llm(0.9))
    cal = await author_trade_plan(
        "AAPL", "daily", ResearchConfig(data_root=tmp_path, calibrated_confidence_in_ev_enabled=True), _Tools(), _Llm(0.9))
    assert cal.trade_score.ev_score < raw.trade_score.ev_score
    assert "used in EV" in _conf_line(cal)


async def test_in_ev_with_too_little_history_changes_nothing(tmp_path):
    _seed(tmp_path, n=10, hits=1)                                      # below the 30 floor
    raw = await author_trade_plan("AAPL", "daily", ResearchConfig(data_root=tmp_path), _Tools(), _Llm(0.9))
    cal = await author_trade_plan(
        "AAPL", "daily", ResearchConfig(data_root=tmp_path, calibrated_confidence_in_ev_enabled=True), _Tools(), _Llm(0.9))
    assert cal.trade_score.ev_score == raw.trade_score.ev_score
    assert "raw_insufficient_sample" in _conf_line(cal)


async def test_no_database_means_no_database_is_created_and_no_line_claims_calibration(tmp_path):
    plan = await author_trade_plan("AAPL", "daily", ResearchConfig(data_root=tmp_path), _Tools(), _Llm(0.9))
    assert not (tmp_path / "strategy_store.db").exists()
    assert "raw_no_map" in _conf_line(plan) or "raw_insufficient_sample" in _conf_line(plan)


async def test_a_broken_store_never_breaks_authoring(tmp_path):
    (tmp_path / "strategy_store.db").write_bytes(b"this is not sqlite")
    plan = await author_trade_plan(
        "AAPL", "daily", ResearchConfig(data_root=tmp_path, calibrated_confidence_in_ev_enabled=True), _Tools(), _Llm(0.9))
    assert plan is not None and _conf_line(plan) is None


async def test_confluence_flag_drops_the_forecast_confidence_vote_from_the_real_plan(tmp_path):
    with_vote = await author_trade_plan("AAPL", "daily", ResearchConfig(data_root=tmp_path), _Tools(), _Llm(0.9))
    without = await author_trade_plan(
        "AAPL", "daily", ResearchConfig(data_root=tmp_path, confluence_excludes_forecast_confidence=True), _Tools(), _Llm(0.9))
    assert any(s.signal == "forecast_confidence" for s in with_vote.forecast.signals)
    assert without.trade_score.confluence_score != with_vote.trade_score.confluence_score
