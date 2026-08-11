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

from vinu_research.storage.strategy_store import SqliteStrategyStore


def _research_data_root() -> Path:
    """Mirrors vinu_research/config.py's own resolution exactly, same as
    vinu-agent's research_link.py -- so the in-process path always points
    at the same data vinu-research's own server process would have used."""
    raw = os.environ.get("VINU_RESEARCH_DATA_ROOT", "").strip()
    return Path(raw) if raw else Path.cwd() / "data"


def get_strategy_store() -> SqliteStrategyStore:
    return SqliteStrategyStore(_research_data_root() / "strategy_store.db")
