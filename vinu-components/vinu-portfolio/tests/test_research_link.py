"""item #4 (system-wide-audit-and-design): get_maturity_assessment() is a
thin wrapper around vinu-research's own already-tested assess() -- this
just confirms the wrapper wires the real in-process strategy_store
correctly, not a re-test of assess()'s own tier logic (see vinu-research's
own tests/test_maturity_assessor.py for that)."""

from __future__ import annotations

import os

from vinu_portfolio.research_link import get_maturity_assessment


def test_empty_strategy_store_reports_cold_start(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp_path))
    assessment = get_maturity_assessment()
    assert assessment.tier == "cold_start"
    assert assessment.n_real_trades == 0


def test_agent_data_root_is_never_consulted(tmp_path, monkeypatch) -> None:
    # vinu-portfolio has no configured path to vinu-agent's
    # paper_performance.db -- confirms this wrapper always passes
    # agent_data_root=None rather than guessing at one.
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp_path))
    assessment = get_maturity_assessment()
    assert assessment.n_paper_trading_days == 0
