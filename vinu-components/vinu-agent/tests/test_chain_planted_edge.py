"""The whole back half of the pipeline on SYNTHETIC prices with a planted edge, in isolated stores.

What is synthetic: the price series (seeded random numbers, built here, never written to any real store). What is real:
the simulator that backtests the strategy, the deflated Sharpe, the bar-size verdict, the promotion bar, the artifact
writer, the risk gatekeeper hook, the capital allocator hook, the order guard and the kill switch. A series with NO edge
goes through the same path and must be rejected, so a pass here means the chain can say no as well as yes.

Nothing here touches data/ or the running stack: stores are temp files, the kill switch files are redirected to tmp_path.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from vinu_agent.agent.capital_allocator_hook import apply_capital_allocator_decision
from vinu_agent.agent.research_artifact_writer import write_artifact_from_research_pass
from vinu_agent.agent.risk_gatekeeper_hook import apply_risk_gatekeeper_verdict
from vinu_agent.broker import kill_switch
from vinu_agent.broker.daily_limits import DailyLimitStore
from vinu_agent.broker.guard_codes import ReasonCode
from vinu_agent.broker.mandate import TradingMandate
from vinu_agent.broker.order_guard import OrderGuard
from vinu_research.bar_validation import _row
from vinu_research.config import ResearchConfig
from vinu_research.generator import generate_strategy
from vinu_research.models import ArtifactStatus
from vinu_research.promotion import meets_promotion_bar
from vinu_research.storage.strategy_store import SqliteStrategyStore
from vinu_research.walk_forward import deflated_sharpe_ratio
from vinu_simulator.engine.custom_sim import simulate_custom
from vinu_simulator.models.simulation import SimulationConfig

SYMBOL = "SYNTH"
N = 2000
LEG = 40


def synthetic_prices(*, planted_edge: bool, seed: int = 11) -> pd.DataFrame:
    """Daily OHLCV. With the edge: long persistent legs (up, then down, ...) a trend follower can ride. Without: noise."""
    rng = np.random.default_rng(seed)
    if planted_edge:
        drift = np.repeat(np.tile([0.006, -0.005], N // (2 * LEG) + 1), LEG)[:N]
        rets = drift + rng.normal(0, 0.008, N)
    else:
        rets = rng.normal(0, 0.012, N)
    close = 100 * np.exp(np.cumsum(rets))
    idx = pd.bdate_range("2019-01-01", periods=N)
    return pd.DataFrame({"open": close, "high": close * 1.004, "low": close * 0.996, "close": close,
                         "volume": np.full(N, 5_000_000.0)}, index=idx)


def _backtest(code: str, prices: pd.DataFrame):
    scope: dict = {}
    exec(code, scope)  # noqa: S102 -- the project's own recipe template
    cfg = SimulationConfig(strategy_name="UserStrategy", start_date=str(prices.index[0].date()),
                           end_date=str(prices.index[-1].date()), allow_short=False)
    return simulate_custom(scope["UserStrategy"], [SYMBOL], {SYMBOL: prices}, cfg)


def measured_bar_evidence(code: str, prices: pd.DataFrame, config: ResearchConfig) -> dict:
    """The per-bar verdict from the project's own `_row`, fed with numbers the real simulator measured here."""
    full = _backtest(code, prices)
    sharpe = float(full.metrics.get("sharpe_ratio", 0.0))
    holdout = _backtest(code, prices.iloc[int(N * 0.75):])
    stress = _backtest(code, prices.iloc[int(N * 0.40): int(N * 0.60)])
    run = {
        "id": 1, "symbol": SYMBOL, "total_iterations": 1,
        "outcome_status": "passed" if sharpe > 0.5 else "no_strategy_found",
        "best_sharpe": sharpe,
        "deflated_sharpe": deflated_sharpe_ratio(
            sharpe=sharpe, n_trials=1, n_obs=len(full.daily_returns), skew=float(full.metrics.get("skewness", 0.0)),
            excess_kurtosis=float(full.metrics.get("kurtosis", 0.0))),
        "holdout_passed": bool(holdout.metrics.get("sharpe_ratio", 0.0) > 0),
        "stress_test_passed": bool(stress.metrics.get("max_drawdown", 0.0) > -0.35),
        "pbo": None, "diagnosis": "",
        "attempt": {"sharpe": sharpe, "max_drawdown": float(full.metrics.get("max_drawdown", 0.0)),
                    "total_return": float(full.metrics.get("total_return", 0.0)),
                    "trade_count": len(full.trades), "win_rate": float(full.metrics.get("win_rate", 0.0) or 0.0)},
    }
    row = _row("1d", ("synthetic", "synthetic"), run, config)
    return {"bars": [row], "passing_bars": ["1d"] if row["eligible"] else [],
            "chosen": row if row["eligible"] else None, "chosen_bar": "1d" if row["eligible"] else None}


@pytest.fixture
def store(tmp_path):
    s = SqliteStrategyStore(tmp_path / "strategy_store.db")
    yield s
    s.close()


@pytest.fixture(autouse=True)
def isolated_kill_switch(tmp_path, monkeypatch):
    from vinu_agent.broker.audit_ledger import HashChainedLedger, reset_safety_ledger

    monkeypatch.setattr(kill_switch, "KILL_SWITCH_PATH", tmp_path / "halt")
    monkeypatch.setattr(kill_switch, "KILL_SWITCH_DIR", tmp_path / "halt.d")
    monkeypatch.setattr(kill_switch, "KILL_SWITCH_LOCK_PATH", tmp_path / "halt.lock")
    reset_safety_ledger(HashChainedLedger(tmp_path / "safety_ledger.jsonl"))
    yield
    reset_safety_ledger(None)


@pytest.fixture(autouse=True)
def isolated_guard_stores():
    from vinu_agent.broker.symbol_limits import SymbolLimitStore, reset_limit_store
    from vinu_agent.broker.symbol_overrides import SymbolOverrideStore, reset_override_store

    reset_override_store(SymbolOverrideStore(":memory:"))
    reset_limit_store(SymbolLimitStore(":memory:"))
    yield
    reset_override_store(None)
    reset_limit_store(None)


def _guard() -> OrderGuard:
    broker = MagicMock()
    broker.get_account.return_value = MagicMock(equity=100_000.0, cash=100_000.0, portfolio_value=100_000.0,
                                                buying_power=100_000.0)
    mandate = TradingMandate(max_position_pct=1.0, require_active_artifact=True, require_market_open=False)
    return OrderGuard(mandate=mandate, broker=broker, daily_limit_store=DailyLimitStore(":memory:"),
                      portfolio_api_url="http://127.0.0.1:9")


def _order(store, side="buy"):
    with patch("vinu_agent.broker.research_link.get_strategy_store", return_value=store):
        return _guard().check(SYMBOL, side, qty=10, price=100.0)


def _pass_content(code: str) -> str:
    body = {"verdict": "PASS", "symbol": SYMBOL, "sharpe": 9.9, "max_drawdown": -0.01, "strategy_code": code}
    return "VERDICT: PASS\n```json\n" + json.dumps(body) + "\n```"


def _gatekeeper(artifact_id: str) -> str:
    body = {"verdict": "APPROVED", "artifact_id": artifact_id, "approved_size": 10_000.0}
    return "```json\n" + json.dumps(body) + "\n```"


def _allocator(artifact_id: str) -> str:
    body = {"candidates": [{"artifact_id": artifact_id, "funded": True, "amount": 10_000.0}]}
    return "```json\n" + json.dumps(body) + "\n```"


CODE = generate_strategy(recipe="crossover", params={"fast_period": 5, "slow_period": 20})


def _written(store, evidence, run_id):
    return write_artifact_from_research_pass(_pass_content(CODE), strategy_store=store, source_run_id=run_id,
                                             bar_validator=lambda *a: evidence)


def test_planted_edge_walks_the_whole_chain_and_the_safety_stops_hold(store):
    config = ResearchConfig()
    evidence = measured_bar_evidence(CODE, synthetic_prices(planted_edge=True), config)
    assert evidence["chosen_bar"] == "1d", evidence["bars"][0]["reasons"]

    # 1 writer: the model typed Sharpe 9.9; the stored numbers are the measured ones, with the bar size
    artifact_id = _written(store, evidence, "syn1")
    art = store.get_artifact(artifact_id)
    assert art.status == ArtifactStatus.BENCHING and art.bar_interval == "1d"
    assert art.initial_sharpe == pytest.approx(evidence["chosen"]["sharpe"]) and art.initial_sharpe != 9.9
    assert meets_promotion_bar(art, config).eligible

    # an order is refused while the strategy is only BENCHING
    refused = _order(store)
    assert not refused and refused.code == ReasonCode.NO_ACTIVE_ARTIFACT

    # 2 risk gatekeeper approves -> PEND ; 3 capital allocator funds -> ACTIVE
    assert apply_risk_gatekeeper_verdict(_gatekeeper(artifact_id), strategy_store=store) == artifact_id
    assert store.get_artifact(artifact_id).status == ArtifactStatus.PEND
    assert apply_capital_allocator_decision(_allocator(artifact_id), strategy_store=store) == artifact_id
    assert store.get_artifact(artifact_id).status == ArtifactStatus.ACTIVE

    # 4 order guard now allows the order; the kill switch stops it; resume allows it again
    assert _order(store)
    kill_switch.halt_trading(scope=SYMBOL)
    halted = _order(store)
    assert not halted and halted.code == ReasonCode.KILL_SWITCH_HALT
    kill_switch.resume_trading(scope=SYMBOL)
    kill_switch.halt_trading()                                            # a global halt too
    halted = _order(store)
    assert not halted and halted.code == ReasonCode.KILL_SWITCH_HALT
    kill_switch.resume_trading()
    assert _order(store)


def test_a_kill_switch_engaged_at_funding_time_holds_the_strategy_as_pendblock(store):
    evidence = measured_bar_evidence(CODE, synthetic_prices(planted_edge=True), ResearchConfig())
    artifact_id = _written(store, evidence, "syn2")
    apply_risk_gatekeeper_verdict(_gatekeeper(artifact_id), strategy_store=store)
    kill_switch.halt_trading(scope=SYMBOL)
    assert apply_capital_allocator_decision(_allocator(artifact_id), strategy_store=store) is None
    assert store.get_artifact(artifact_id).status == ArtifactStatus.PENDBLOCK
    assert not _order(store)


def test_no_edge_is_rejected_by_code_and_the_guard_refuses_the_symbol(store):
    config = ResearchConfig()
    evidence = measured_bar_evidence(CODE, synthetic_prices(planted_edge=False), config)
    assert evidence["chosen_bar"] is None
    artifact_id = _written(store, evidence, "syn3")
    art = store.get_artifact(artifact_id)
    assert art.status == ArtifactStatus.DISABLED and art.bar_interval == ""
    assert not meets_promotion_bar(art, config).eligible
    refused = _order(store)
    assert not refused and refused.code == ReasonCode.NO_ACTIVE_ARTIFACT


def test_a_bad_strategy_forced_through_the_gatekeeper_still_cannot_be_funded(store):
    """Defence in depth: the allocator re-checks the stored numbers, so a bad strategy forced to PEND stays unfunded."""
    evidence = measured_bar_evidence(CODE, synthetic_prices(planted_edge=False), ResearchConfig())
    art_id = _written(store, evidence, "syn4")
    art = store.get_artifact(art_id)
    art.status = ArtifactStatus.BENCHING                                   # forced back, as a rogue or buggy path might
    store.upsert_artifact(art)
    apply_risk_gatekeeper_verdict(_gatekeeper(art_id), strategy_store=store)
    assert apply_capital_allocator_decision(_allocator(art_id), strategy_store=store) is None
    assert store.get_artifact(art_id).status != ArtifactStatus.ACTIVE
    assert not _order(store)


@pytest.fixture(autouse=True)
def _regular_session_whatever_the_wall_clock_says(monkeypatch):
    """The guard now judges the trading session from the broker clock (`vinu_infra.sessions`). These tests were written for the
    regular session and must not depend on what time of day they run; the session rules have their own tests
    (test_session_orders.py)."""
    monkeypatch.setattr("vinu_agent.broker.order_guard.session_of", lambda ts: "regular")
