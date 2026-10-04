"""A live-decision strategy must pass the system's own research gates before it can trade (strategy_validation.py)."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from vinu_research.config import ResearchConfig
from vinu_research.strategy_validation import (
    StrategyValidationStore, conditions_to_code, validate_strategy,
)

PULLBACK = [
    {"source": "live_indicators", "key": "dist_from_sma_50", "operator": "gt", "value": 0},
    {"source": "live_indicators", "key": "dist_from_sma_5", "operator": "lt", "value": 0},
    {"source": "live_indicators", "key": "adx_14", "operator": "gt", "value": 20},
]


def _weights(code: str, data: pd.DataFrame) -> pd.Series:
    """Run generated code against a stand-in BaseStrategy, the way the simulator would."""
    import sys
    import types
    mod = types.ModuleType("vinu_simulator.engine.strategies")
    mod.BaseStrategy = object
    pkg = types.ModuleType("vinu_simulator"); eng = types.ModuleType("vinu_simulator.engine")
    saved = {k: sys.modules.get(k) for k in ("vinu_simulator", "vinu_simulator.engine", "vinu_simulator.engine.strategies")}
    sys.modules.update({"vinu_simulator": pkg, "vinu_simulator.engine": eng, "vinu_simulator.engine.strategies": mod})
    try:
        ns: dict = {}
        exec(code, ns)
        return ns["UserStrategy"]().generate_weights(data)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v


# ----------------------------------------------------------------------------------------------- conditions -> code

def test_pullback_conditions_become_code_that_holds_for_n_bars_after_each_setup():
    code, indicators, problems = conditions_to_code(PULLBACK, hold=2)
    assert problems == [] and code is not None and "class UserStrategy" in code
    assert sorted(indicators) == ["adx_14", "sma_5", "sma_50"]          # derived dist_from_* needs the base averages
    # bar 0 is a setup: close 11 is above sma_50 (10), below sma_5 (12), ADX 25. Every other bar fails ADX.
    data = pd.DataFrame({
        "close": [11.0, 11, 11, 11, 11], "sma_50": [10.0] * 5, "sma_5": [12.0] * 5, "adx_14": [25.0, 10, 10, 10, 10],
    })
    w = _weights(code, data)
    assert list(w) == [0.0, 1.0, 1.0, 0.0, 0.0]        # the next 2 bars (hold = 2), then flat; nothing on the setup bar itself


def test_a_second_setup_inside_the_hold_extends_it():
    code, _, _ = conditions_to_code(PULLBACK[:1], hold=2)             # only: close above its 50 bar average
    data = pd.DataFrame({"close": [11.0, 9, 11, 9, 9, 9], "sma_50": [10.0] * 6})   # setups at bars 0 and 2
    assert list(_weights(code, data)) == [0.0, 1.0, 1.0, 1.0, 1.0, 0.0]   # setup at 0 holds bars 1-2, setup at 2 holds bars 3-4


def test_between_eq_and_in_are_supported():
    code, indicators, problems = conditions_to_code(
        [{"key": "rsi_14", "operator": "between", "value": [35, 60]}, {"key": "adx_14", "operator": "in", "value": [20, 30]}], hold=1)
    assert problems == [] and sorted(indicators) == ["adx_14", "rsi_14"]
    data = pd.DataFrame({"close": [1.0, 1, 1], "rsi_14": [50.0, 70, 50], "adx_14": [20.0, 20, 25]})
    assert list(_weights(code, data)) == [0.0, 1.0, 0.0]               # only bar 0 has rsi in [35,60] and adx in {20,30}


@pytest.mark.parametrize("conditions,reason", [
    ([{"key": "bollinger_percent_b", "operator": "gt", "value": 0.5}], "no backtest equivalent"),
    ([{"key": "adx_14", "operator": "crosses", "value": 20}], "operator or value that cannot be tested"),
    ([{"key": "adx_14", "operator": "gt", "value": "high"}], "operator or value that cannot be tested"),
    ([], "nothing to test"),
])
def test_what_cannot_be_tested_gives_no_code_and_a_reason(conditions, reason):
    code, indicators, problems = conditions_to_code(conditions, hold=20)
    assert code is None and indicators == [] and any(reason in p for p in problems)


def test_one_untestable_condition_makes_the_whole_strategy_untestable():
    code, _, problems = conditions_to_code(PULLBACK + [{"key": "obv", "operator": "gt", "value": 0}], hold=20)
    assert code is None and len(problems) == 1


# --------------------------------------------------------------------------------------------------- the verdicts

class FakeService:
    """Stands in for ResearchService: records the calls and answers per ticker."""

    def __init__(self, tmp_path, answers: dict):
        self.strategy_validation_store = StrategyValidationStore(tmp_path / "v.db")
        self.config = ResearchConfig(data_root=tmp_path)
        self.answers, self.calls = answers, []
        self._storage = SimpleNamespace(get_run=lambda run_id: self.records[run_id])
        self.records = {}

    async def _run_in_thread(self, fn, *args):
        return fn(*args)

    async def run_research(self, **kw):
        self.calls.append(kw)
        a = self.answers[kw["symbol"]]
        if isinstance(a, Exception):
            raise a
        rid = len(self.calls)
        if a.get("skipped"):
            return {"id": rid, "outcome_status": "no_strategy_found", "total_iterations": 0, "best_sharpe": 0.0,
                    "report_md": "## Symbol " + kw["symbol"] + " is exhausted\n\nSkipping."}
        self.records[rid] = SimpleNamespace(symbol=kw["symbol"], best_sharpe=a["sharpe"], deflated_sharpe=a["dsr"],
                                            holdout_passed=a["holdout"], stress_test_passed=a["stress"], pbo=a["pbo"])
        return {"id": rid, "total_iterations": 1, "outcome_status": a.get("outcome", "passed"), "best_sharpe": a["sharpe"],
                "deflated_sharpe": a["dsr"], "holdout_passed": a["holdout"], "stress_test_passed": a["stress"], "diagnosis": ""}


GOOD = {"sharpe": 1.2, "dsr": 0.97, "holdout": True, "stress": True, "pbo": 0.3}
BAD = {"sharpe": 0.3, "dsr": 0.40, "holdout": False, "stress": True, "pbo": 0.3, "outcome": "no_strategy_found"}
DEFINITION = {"name": "pullback_1h", "schedule": "1h", "universe": ["AAPL", "MSFT", "GOOGL", "AMZN", "META"],
              "must_conditions": PULLBACK, "live_decision_max_hold_bars": 20}


@pytest.mark.asyncio
async def test_three_of_five_passing_validates_and_only_those_tickers_are_eligible(tmp_path):
    svc = FakeService(tmp_path, {"AAPL": GOOD, "MSFT": GOOD, "GOOGL": GOOD, "AMZN": BAD, "META": BAD})
    out = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert out["status"] == "validated" and out["detail"]["eligible_tickers"] == ["AAPL", "GOOGL", "MSFT"]
    assert out["detail"]["pass_share"] == pytest.approx(0.6)
    # each ticker was researched on the strategy's own bar size, for one iteration, with the generated code
    assert all(c["interval"] == "1h" and c["max_iterations"] == 1 and "class UserStrategy" in c["strategy_code"] for c in svc.calls)
    assert svc.strategy_validation_store.list()[0]["status"] == "validated"


@pytest.mark.asyncio
async def test_two_of_five_is_rejected(tmp_path):
    svc = FakeService(tmp_path, {"AAPL": GOOD, "MSFT": GOOD, "GOOGL": BAD, "AMZN": BAD, "META": BAD})
    out = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert out["status"] == "rejected" and out["detail"]["pass_share"] == pytest.approx(0.4)


@pytest.mark.asyncio
async def test_a_run_that_clears_the_bar_numbers_but_the_loop_did_not_pass_is_not_eligible(tmp_path):
    svc = FakeService(tmp_path, {t: {**GOOD, "outcome": "no_strategy_found"} for t in DEFINITION["universe"]})
    out = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert out["status"] == "rejected" and not out["detail"]["eligible_tickers"]


@pytest.mark.asyncio
async def test_a_ticker_that_errors_is_not_eligible_and_does_not_hide_the_others(tmp_path):
    svc = FakeService(tmp_path, {"AAPL": GOOD, "MSFT": GOOD, "GOOGL": GOOD, "AMZN": RuntimeError("simulator down"), "META": GOOD})
    out = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert out["status"] == "validated" and "AMZN" not in out["detail"]["eligible_tickers"]
    assert "simulator down" in out["detail"]["per_ticker"]["AMZN"]["reasons"][0]


@pytest.mark.asyncio
@pytest.mark.parametrize("change,reason", [
    ({"schedule": "whenever"}, "not a bar size"),
    ({"must_conditions": []}, "nothing to test"),
    ({"must_conditions": [{"key": "obv", "operator": "gt", "value": 0}]}, "no backtest equivalent"),
    ({"universe": []}, "no tickers"),
])
async def test_what_cannot_be_tested_is_unvalidatable_and_never_reaches_research(tmp_path, change, reason):
    svc = FakeService(tmp_path, {})
    out = await validate_strategy(svc, {**DEFINITION, **change}, "2022-01-03", "2026-10-02")
    assert out["status"] == "unvalidatable" and any(reason in r for r in out["detail"]["reasons"])
    assert svc.calls == []


@pytest.mark.asyncio
async def test_the_fingerprint_changes_when_the_rules_change(tmp_path):
    svc = FakeService(tmp_path, {t: GOOD for t in DEFINITION["universe"]})
    a = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    changed = {**DEFINITION, "must_conditions": [{**PULLBACK[2], "value": 25}] + PULLBACK[:2]}
    b = await validate_strategy(svc, changed, "2022-01-03", "2026-10-02")
    assert a["fingerprint"] != b["fingerprint"]


@pytest.mark.asyncio
async def test_validation_runs_are_flagged_so_research_ignores_the_exhausted_flag(tmp_path):
    svc = FakeService(tmp_path, {t: GOOD for t in DEFINITION["universe"]})
    await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert svc.calls and all(c["validation"] is True for c in svc.calls)


@pytest.mark.asyncio
async def test_a_ticker_research_skipped_is_not_tested_never_rejected(tmp_path):
    """Research answered 'symbol is exhausted, skipping' for every ticker: nothing was tested, so the verdict is
    'not_tested' (still blocked), not 'rejected' (which would claim the strategy was judged and failed)."""
    svc = FakeService(tmp_path, {t: {"skipped": True} for t in DEFINITION["universe"]})
    out = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert out["status"] == "not_tested" and out["detail"]["eligible_tickers"] == []
    first = out["detail"]["per_ticker"]["AAPL"]
    assert first["tested"] is False and "research did not run it" in first["reasons"][0] and "exhausted" in first["reasons"][0]


@pytest.mark.asyncio
async def test_some_skipped_and_the_rest_failing_is_a_rejection_of_what_was_tested(tmp_path):
    svc = FakeService(tmp_path, {"AAPL": {"skipped": True}, "MSFT": BAD, "GOOGL": BAD, "AMZN": BAD, "META": BAD})
    out = await validate_strategy(svc, DEFINITION, "2022-01-03", "2026-10-02")
    assert out["status"] == "rejected"
