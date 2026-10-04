"""A run where no iteration passes gets a deterministic 'why' (no edge / edge eaten by costs / survives costs) from a
zero-cost twin of the best attempt, in the report, the summary and the response."""

from __future__ import annotations

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.llm import ResearchLlmClient
from vinu_research.loop import StrategyResearchLoop
from vinu_research.models import (
    BacktestMetrics, BacktestResult, CriticFeedback, IterationRecord, ResearchResult,
)
from vinu_research.service import ResearchService
from vinu_research.tools import ResearchTools


def _bt(sharpe, ret, trades=98):
    return BacktestResult(run_id="x", strategy_name="UserStrategy",
                          metrics=BacktestMetrics(sharpe_ratio=sharpe, total_return=ret),
                          benchmark_metrics={}, trade_count=trades, equity_points=300, raw={})


def _attempt():
    return IterationRecord(iteration=1, strategy_code="class UserStrategy: pass", result=_bt(-0.22, -0.17),
                           critique=CriticFeedback(verdict="STOP", reasoning="gate", suggestions=[]))


async def _run(tmp_path, monkeypatch, net, gross):
    async def fake_loop(self, **kw):
        return ResearchResult(symbol="AAPL", from_date="2025-01-01", to_date="2026-01-01", user_idea="x",
                              iterations=[_attempt()], best_result=None, best_iteration=-1, total_iterations=1,
                              report_md="REPORT", outcome_status="no_strategy_found")

    seen = []

    async def fake_backtest(self, **kw):
        seen.append(kw)
        free = kw.get("transaction_cost_pct") == 0.0 and kw.get("slippage_pct") == 0.0
        return gross if free else net

    async def fake_summary(self, **kw):
        return "LLM SUMMARY"

    monkeypatch.setattr(StrategyResearchLoop, "run", fake_loop)
    monkeypatch.setattr(ResearchTools, "run_backtest", fake_backtest)
    monkeypatch.setattr(ResearchLlmClient, "summarize_run", fake_summary)
    svc = ResearchService(config=ResearchConfig(data_root=tmp_path, llm_enabled=True))
    out = await svc.run_research(user_idea="x", strategy_code=None, symbol="AAPL",
                                 from_date="2025-01-01", to_date="2026-01-01")
    return out, seen


@pytest.mark.asyncio
async def test_edge_eaten_by_costs_is_named_with_the_numbers(tmp_path, monkeypatch):
    out, seen = await _run(tmp_path, monkeypatch, _bt(-0.22, -0.170), _bt(0.34, 0.207))
    assert "edge, but trading costs eat it" in out["diagnosis"] and "37.7%" in out["diagnosis"]
    assert out["diagnosis"] in out["summary_text"] and out["summary_text"].startswith("LLM SUMMARY")
    assert out["diagnosis"] in out["report_md"] and out["report_md"].startswith("REPORT")
    assert len(seen) == 2 and seen[0].get("transaction_cost_pct") is None   # one real-cost run, one zero-cost twin


@pytest.mark.asyncio
async def test_no_edge_is_named_as_not_a_cost_problem(tmp_path, monkeypatch):
    out, _ = await _run(tmp_path, monkeypatch, _bt(-2.95, -0.453), _bt(-0.49, -0.118))
    assert "shows no edge" in out["diagnosis"] and "costs are not the cause" in out["diagnosis"]


@pytest.mark.asyncio
async def test_a_failed_twin_never_fails_the_run(tmp_path, monkeypatch):
    out, _ = await _run(tmp_path, monkeypatch, None, None)
    assert out["diagnosis"] == "" and out["status"] == "done"
