"""One strategy on every bar size, judged by code; the numbers come from the run's records."""

from __future__ import annotations

import asyncio
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from vinu_research.bar_validation import BAR_WINDOW_DAYS, choose_bar, validate_across_bars
from vinu_research.config import ResearchConfig
from vinu_research.models import Artifact
from vinu_research.server.app import create_app

CODE = "class UserStrategy:\n    pass\n"


def _run(*, passed=True, trades=60, deflated=1.2, holdout=True, stress=True, pbo=None, sharpe=0.9):
    return {
        "id": 1, "symbol": "AMD", "total_iterations": 1, "outcome_status": "passed" if passed else "no_strategy_found",
        "best_sharpe": sharpe if passed else 0.0, "deflated_sharpe": deflated if passed else 0.0,
        "holdout_passed": holdout, "stress_test_passed": stress, "pbo": pbo, "diagnosis": "",
        "attempt": {"sharpe": sharpe, "max_drawdown": -0.1, "total_return": 0.2, "trade_count": trades, "win_rate": 0.4},
    }


class FakeService:
    def __init__(self, by_interval, config=None):
        self.config = config or ResearchConfig()
        self.by_interval = by_interval
        self.calls = []

    async def run_research(self, **kw):
        self.calls.append(kw)
        out = self.by_interval[kw["interval"]]
        if isinstance(out, Exception):
            raise out
        return out


def _validate(by_interval, **kw):
    svc = FakeService(by_interval)
    return svc, asyncio.run(validate_across_bars(svc, symbol="AMD", strategy_code=CODE, to_date="2026-10-01", **kw))


def test_same_code_is_run_unchanged_on_every_bar_size_with_its_own_window():
    svc, out = _validate({b: _run() for b in BAR_WINDOW_DAYS})
    assert sorted(c["interval"] for c in svc.calls) == sorted(BAR_WINDOW_DAYS)
    assert {c["strategy_code"] for c in svc.calls} == {CODE}
    assert all(c["max_iterations"] == 1 and c["validation"] is True for c in svc.calls)
    spans = {c["interval"]: (c["from_date"], c["to_date"]) for c in svc.calls}
    assert spans["15m"][0] == "2025-10-01" and spans["1d"][0] < spans["15m"][0]
    assert out["passing_bars"] and out["chosen_bar"]


def test_too_few_trades_is_not_eligible_even_when_everything_else_passes():
    _, out = _validate({"1d": _run(trades=12), "4h": _run(trades=12), "1h": _run(trades=29), "15m": _run(trades=30)})
    assert out["passing_bars"] == ["15m"]
    short = next(r for r in out["bars"] if r["interval"] == "1d")
    assert any("12 trades" in reason for reason in short["reasons"])


def test_failing_loop_or_holdout_or_stress_or_low_deflated_sharpe_blocks_that_bar():
    _, out = _validate({
        "1d": _run(passed=False), "4h": _run(holdout=False), "1h": _run(stress=False), "15m": _run(deflated=0.5),
    })
    assert out["passing_bars"] == [] and out["chosen_bar"] is None
    reasons = {r["interval"]: " ".join(r["reasons"]) for r in out["bars"]}
    assert "did not pass" in reasons["1d"] and "never computed" not in reasons["1d"]
    assert "holdout" in reasons["4h"]
    assert "stress" in reasons["1h"]
    assert "deflated_sharpe" in reasons["15m"]


def test_missing_holdout_or_stress_is_a_rejection_not_a_pass():
    _, out = _validate({b: _run(holdout=None, stress=None) for b in BAR_WINDOW_DAYS})
    assert out["passing_bars"] == []


def test_no_parameter_trials_means_pbo_is_waived_and_says_so_but_a_real_high_pbo_still_blocks():
    _, out = _validate({"1d": _run(pbo=None), "4h": _run(pbo=0.9), "1h": _run(pbo=0.2), "15m": _run(passed=False)})
    rows = {r["interval"]: r for r in out["bars"]}
    assert rows["1d"]["eligible"] and rows["1d"]["pbo_waived"] is True
    assert not rows["4h"]["eligible"] and "PBO" in " ".join(rows["4h"]["reasons"])
    assert rows["1h"]["eligible"] and rows["1h"]["pbo_waived"] is False


def test_one_bar_size_crashing_does_not_hide_the_others():
    _, out = _validate({"1d": RuntimeError("simulator down"), "4h": _run(), "1h": _run(), "15m": _run()})
    row = next(r for r in out["bars"] if r["interval"] == "1d")
    assert row["tested"] is False and "simulator down" in row["reasons"][0]
    assert "4h" in out["passing_bars"]


def test_a_run_that_never_executed_is_not_tested_never_eligible():
    run = _run()
    run["total_iterations"] = 0
    _, out = _validate({b: run for b in BAR_WINDOW_DAYS})
    assert all(r["tested"] is False and r["eligible"] is False for r in out["bars"])


def test_choose_bar_prefers_the_highest_deflated_sharpe_among_eligible():
    rows = [
        {"interval": "1d", "eligible": True, "deflated_sharpe": 0.96, "sharpe": 2.0},
        {"interval": "4h", "eligible": True, "deflated_sharpe": 1.4, "sharpe": 0.5},
        {"interval": "1h", "eligible": False, "deflated_sharpe": 9.0, "sharpe": 9.0},
    ]
    assert choose_bar(rows)["interval"] == "4h"


def test_artifact_keeps_bar_size_and_evidence_through_the_store(strategy_store):
    a = Artifact.create("strategy", "AMD-x", universe=["AMD"])
    a.bar_interval, a.bar_evidence = "4h", '{"bars": []}'
    strategy_store.upsert_artifact(a)
    back = strategy_store.get_artifact(a.artifact_id)
    assert (back.bar_interval, back.bar_evidence) == ("4h", '{"bars": []}')
    assert Artifact.create("strategy", "y").bar_interval == ""


def test_route_rejects_code_that_defines_no_strategy_class(service):
    client = TestClient(create_app(service))
    r = client.post("/research/validate-code", json={"symbol": "AMD", "strategy_code": "x = 1"})
    assert r.status_code == 422


def test_normaliser_accepts_the_class_name_and_missing_imports_the_agent_prompt_produces():
    from vinu_research.bar_validation import normalise_strategy_code

    out = normalise_strategy_code("class Strategy(BaseStrategy):\n    def generate_weights(self, data):\n        return data['close'] * 0\n")
    assert "class UserStrategy(BaseStrategy)" in out and "import pandas as pd" in out
    assert out.startswith("from __future__ import annotations")
    ns: dict = {}
    exec(compile(out, "<s>", "exec"), ns)  # noqa: S102
    assert "UserStrategy" in ns


def test_normaliser_leaves_ready_code_alone_and_rejects_ambiguous_or_broken_code():
    from vinu_research.bar_validation import normalise_strategy_code

    ready = "import pandas as pd\nfrom vinu_simulator.engine.strategies import BaseStrategy\n\nclass UserStrategy(BaseStrategy):\n    pass\n"
    assert normalise_strategy_code(ready) == ready
    with pytest.raises(ValueError, match="one class"):
        normalise_strategy_code("class A(BaseStrategy):\n    pass\nclass B(BaseStrategy):\n    pass\n")
    with pytest.raises(ValueError, match="not valid Python"):
        normalise_strategy_code("def (:")
