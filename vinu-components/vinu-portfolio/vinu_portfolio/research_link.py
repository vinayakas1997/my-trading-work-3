"""Direct, in-process link to vinu-research's real strategy/hypothesis
stores -- mirrors vinu-agent's own vinu_agent/broker/research_link.py
(same in-process-first, HTTP-fallback migration, extended to this
codebase's own 3 independent HTTP call sites in service.py --
_list_llm_strategies/_fetch_outcome_confidence/_fetch_trade_plan --
found not to be covered by the original migration doc at all). Requires
vinu-research (and its own transitive deps -- vinu-stock-price,
vinu-tools, vinu-simulator) to be installed; vinu-portfolio's Dockerfile
installs them. If vinu-research is not importable, every call site here
raises and its own try/except falls back to HTTP.
"""

from __future__ import annotations

import os
from pathlib import Path

from vinu_research.maturity_assessor import MaturityAssessment
from vinu_research.maturity_assessor import assess as _assess_maturity
from vinu_research.storage.strategy_store import SqliteStrategyStore


def _research_data_root() -> Path:
    """Mirrors vinu_research/config.py's own resolution exactly, same as
    vinu-agent's research_link.py -- so the in-process path always points
    at the same data vinu-research's own server process would have used."""
    raw = os.environ.get("VINU_RESEARCH_DATA_ROOT", "").strip()
    return Path(raw) if raw else Path.cwd() / "data"


def get_strategy_store() -> SqliteStrategyStore:
    return SqliteStrategyStore(_research_data_root() / "strategy_store.db")


def get_maturity_assessment() -> MaturityAssessment:
    """item #4 (system-wide-audit-and-design): reuses vinu-research's own
    `maturity_assessor.assess()` unchanged, through the same in-process
    bridge `get_strategy_store()` above already established -- not a
    second, independently-derived maturity computation.

    `agent_data_root=None` always: vinu-portfolio has no configured path
    to vinu-agent's `paper_performance.db` (a real dependency this
    service doesn't have today, not an oversight to silently work around
    here). `assess()`'s own docstring already documents this exact
    degraded case -- n_paper_trading_days/n_artifacts_with_paper_history
    fall back to (0, 0), so `cold_start` and `paper_only` become
    indistinguishable, same honest, already-accepted gap its other
    caller (`research-api`'s own HTTP-fallback path) has, not a new one
    introduced here."""
    store = get_strategy_store()
    return _assess_maturity(store, agent_data_root=None)
