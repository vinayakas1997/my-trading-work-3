"""A validation run tests fixed rules: it ignores the 'symbol exhausted' flag and does not feed it. Before this, five
validations in parallel (plus earlier test runs) exhausted every ticker, research then skipped them all, and the validator
reported 'rejected' for strategies that had never been tested."""

from __future__ import annotations

import pytest

from vinu_research.config import ResearchConfig
from vinu_research.loop import StrategyResearchLoop
from vinu_research.models import ResearchResult
from vinu_research.service import ResearchService


async def _run(tmp_path, monkeypatch, validation):
    seen = {"ignore": None, "catalog_updates": 0}

    async def fake_loop(self, **kw):
        seen["ignore"] = self._config.ignore_symbol_exhaustion
        return ResearchResult(symbol="AAPL", from_date="2025-01-01", to_date="2026-01-01", user_idea="x", iterations=[],
                              best_result=None, best_iteration=-1, total_iterations=0, report_md="R",
                              outcome_status="no_strategy_found")

    monkeypatch.setattr(StrategyResearchLoop, "run", fake_loop)
    svc = ResearchService(config=ResearchConfig(data_root=tmp_path))
    real = svc._storage.update_catalog_after_run

    def spy(*a, **k):
        seen["catalog_updates"] += 1
        return real(*a, **k)

    monkeypatch.setattr(svc._storage, "update_catalog_after_run", spy)
    await svc.run_research(user_idea="x", strategy_code=None, symbol="AAPL", from_date="2025-01-01",
                           to_date="2026-01-01", validation=validation)
    return seen


@pytest.mark.asyncio
async def test_a_validation_run_ignores_exhaustion_and_does_not_count_toward_it(tmp_path, monkeypatch):
    seen = await _run(tmp_path, monkeypatch, validation=True)
    assert seen == {"ignore": True, "catalog_updates": 0}


@pytest.mark.asyncio
async def test_an_ordinary_run_is_unchanged(tmp_path, monkeypatch):
    seen = await _run(tmp_path, monkeypatch, validation=False)
    assert seen == {"ignore": False, "catalog_updates": 1}
