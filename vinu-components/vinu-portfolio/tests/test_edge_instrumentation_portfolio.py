"""Phase 3 extension: the runtime edge recorder wired into vinu-portfolio -- the drawdown status read and the maturity
read inside compute_daily_allocation, and the allocation-history reads behind GET /portfolio/allocation-history and
/portfolio/not-funded. Each must record the right status, and recording must never change a result.

Notable case: an empty `updated_at` on the drawdown status means the drawdown monitor has NEVER written one, so the
halve / flat / halt ladder is running on its default ("ok") and silently doing nothing; that is recorded as `empty`.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from vinu_infra import pipeline_edge_recorder as rec
from vinu_portfolio.config import PortfolioConfig
from vinu_portfolio.service import PortfolioService
from vinu_portfolio.storage.drawdown_status import DrawdownStatusStore


@pytest.fixture(autouse=True)
def _recorder_root(tmp_path, monkeypatch):
    monkeypatch.delenv("VINU_STRATEGY_EVAL_DATA_ROOT", raising=False)
    monkeypatch.setenv("VINU_EDGE_DATA_ROOT", str(tmp_path / "edges"))
    (tmp_path / "edges").mkdir()
    rec.reset_for_tests()
    yield
    rec.reset_for_tests()


def _state(edge_id):
    store = rec.resolve_edge_status_store()
    return store.get_state(edge_id) if store else None


def _svc(tmp_path, **cfg):
    svc = PortfolioService(config=PortfolioConfig(data_root=tmp_path, max_per_strategy_weight=1.0, **cfg))
    svc.build_portfolio = AsyncMock(return_value={
        "status": "ok", "strategies": [{"name": "a", "kind": "yaml"}],
        "weights": [{"name": "a", "kind": "yaml", "symbol": "AAPL", "target_weight": 1.0}], "correlation_matrix": None,
    })
    svc._fetch_benchmark_regime = AsyncMock(return_value={"status": "unavailable", "regime": None})
    svc._fetch_outcome_confidence = AsyncMock(return_value={"source": "not_tracked", "accuracy": None, "n_entries": 0})
    svc._fetch_account_equity = AsyncMock(return_value=100_000.0)
    svc._fetch_positions = AsyncMock(return_value=[])
    return svc


E_DD = "drawdown_status->portfolio.allocation"
E_MAT = "maturity.status->portfolio.capital"
E_HIST = "portfolio.not_funded_history->portfolio.api"


def test_a_drawdown_monitor_that_never_wrote_is_recorded_empty_and_the_allocation_is_unchanged(tmp_path):
    svc = _svc(tmp_path)
    result = asyncio.run(svc.compute_daily_allocation())
    st = _state(E_DD)
    assert st["status"] == "empty" and "never recorded" in st["last_detail"]
    assert result["drawdown_status"]["action"] == "ok" and result["deployable_equity"] == pytest.approx(100_000.0)


def test_a_recorded_drawdown_status_is_recorded_received_with_its_action(tmp_path):
    svc = _svc(tmp_path)
    DrawdownStatusStore(str(tmp_path / "drawdown_status.db")).record(action="halve", current_drawdown=-0.12, threshold_breached=False)
    result = asyncio.run(svc.compute_daily_allocation())
    st = _state(E_DD)
    assert st["status"] == "received" and "halve" in st["last_detail"]
    assert result["deployable_equity"] == pytest.approx(50_000.0)


def _assessment(tier):
    from vinu_research.maturity_assessor import MaturityAssessment

    return MaturityAssessment(tier=tier, n_real_trades=0, n_paper_trading_days=0, directional_accuracy=0.0, regime_coverage=[])


def test_the_maturity_read_is_recorded_only_when_gating_is_on(tmp_path):
    with patch("vinu_portfolio.research_link.get_maturity_assessment", return_value=_assessment("mature")):
        asyncio.run(_svc(tmp_path).compute_daily_allocation())
    assert _state(E_MAT) is None                                              # off by default: nothing consulted, nothing recorded
    with patch("vinu_portfolio.research_link.get_maturity_assessment", return_value=_assessment("paper_only")):
        asyncio.run(_svc(tmp_path / "b", maturity_capital_gating_enabled=True).compute_daily_allocation())
    st = _state(E_MAT)
    assert st["status"] == "received" and "paper_only" in st["last_detail"]


def test_a_failed_maturity_read_is_recorded_missing_and_still_deploys_full_capital(tmp_path):
    with patch("vinu_portfolio.research_link.get_maturity_assessment", side_effect=RuntimeError("research not importable")):
        result = asyncio.run(_svc(tmp_path, maturity_capital_gating_enabled=True).compute_daily_allocation())
    assert _state(E_MAT)["status"] == "missing" and "research not importable" in _state(E_MAT)["last_detail"]
    assert result["maturity_capital_multiplier"] == 1.0


def test_allocation_history_reads_are_recorded_empty_then_received(tmp_path):
    svc = _svc(tmp_path)
    assert svc.allocation_history_summaries() == [] and _state(E_HIST)["status"] == "empty"
    assert svc.latest_not_funded() is None and _state(E_HIST)["status"] == "empty"
    svc._allocation_history.record_daily_allocation(
        allocation_date="2026-10-03", weights=[{"name": "s", "target_weight": 1.0}], account_equity=1.0, deployable_equity=1.0)
    assert len(svc.allocation_history_summaries()) == 1
    st = _state(E_HIST)
    assert st["status"] == "received" and "1 allocation" in st["last_detail"]
    assert svc.latest_not_funded()["allocation_date"] == "2026-10-03" and _state(E_HIST)["status"] == "received"


def test_a_broken_recorder_changes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(rec, "resolve_edge_status_store", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("recorder down")))
    svc = _svc(tmp_path)
    result = asyncio.run(svc.compute_daily_allocation())
    assert result["deployable_equity"] == pytest.approx(100_000.0) and svc.allocation_history_summaries()
