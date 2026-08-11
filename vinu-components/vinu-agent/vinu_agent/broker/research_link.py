"""Direct, in-process link to vinu-research's real strategy/hypothesis
stores -- replaces HTTP calls to a separately-running vinu-research
service. vinu-research's Python package (models, HypothesisRegistry,
SqliteStrategyStore, promotion gate) is unchanged; only the network hop
is removed.

See New-talk-agents/implementation/00-status.md and
New-talk-agents/implementation/13-vinu-research-in-process-migration.md
for why: vinu-research is being retired as a standalone deployed service,
but its real logic isn't being thrown away or reimplemented -- it's
imported directly instead. As of the 2026-08-11 pass, all real
vinu-agent call sites are migrated to the in-process path (with an HTTP
fallback on any exception, same posture `trade_plan_calibration.py`
already established) -- see component-consolidation-plan.md's own
tracking of which files are done.

Requires vinu-research (and its own transitive deps -- vinu-stock-price,
vinu-tools, vinu-simulator) to actually be installed in whatever process
imports this module. vinu-agent's Dockerfile installs them; a dev/test
environment needs the same packages editable-installed. If vinu-research
is not importable, every in-process call site here raises and its own
try/except falls back to HTTP (or, for the two call sites with no HTTP
fallback at all -- order_guard.py/debrief.py -- fails open/best-effort
per their own documented policy, not a crash).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import Hypothesis
from vinu_research.storage.sqlite_backend import ResearchStorage
from vinu_research.storage.strategy_store import SqliteStrategyStore


def _research_data_root() -> Path:
    """Mirrors vinu_research/config.py's own resolution exactly, so the
    in-process path always points at the same data vinu-research's own
    server process would have used."""
    raw = os.environ.get("VINU_RESEARCH_DATA_ROOT", "").strip()
    return Path(raw) if raw else Path.cwd() / "data"


def get_hypothesis_registry() -> HypothesisRegistry:
    # HypothesisRegistry() already resolves VINU_RESEARCH_DATA_ROOT itself
    # (see hypothesis_registry.py) -- no path to pass here.
    return HypothesisRegistry()


def get_strategy_store() -> SqliteStrategyStore:
    return SqliteStrategyStore(_research_data_root() / "strategy_store.db")


def get_research_storage() -> ResearchStorage:
    return ResearchStorage(_research_data_root() / "research_meta.db")


def get_research_tools(config=None):
    """A fresh ResearchTools per call -- the same primitive routes_sweep.py's
    own `_tools` module-level instance wraps, used for sweep-candidate/grid
    and trade-plan authoring. Callers are responsible for `await
    tools.close()` when done, same as routes_trade_plan.py's own usage."""
    from vinu_research.tools import ResearchTools

    return ResearchTools(config or get_research_config())


def get_research_service():
    """A fresh ResearchService per call -- cheap to construct (just opens
    its own storage/strategy_store handles and an idle httpx.AsyncClient,
    same as the real server process's own module-level `_service`); it
    holds no other state worth caching across calls."""
    from vinu_research.service import ResearchService

    return ResearchService()


def get_research_config():
    """vinu_research.config.load_config() resolves VINU_RESEARCH_DATA_ROOT
    and every other research setting the same way the real server process
    does -- reused as-is (not re-derived) for constructing ResearchTools/
    trade-plan-authoring in-process."""
    from vinu_research.config import load_config

    return load_config()


def serialize_hypothesis(h: Hypothesis) -> dict[str, Any]:
    """Exactly routes_introspect.py's own `_serialize_hypothesis` shape --
    kept in sync deliberately so an in-process caller and an HTTP caller of
    the same data get identical dicts."""
    return {
        "hypothesis_id": h.hypothesis_id,
        "title": h.title,
        "thesis": h.thesis,
        "status": h.status.value,
        "universe": h.universe,
        "strategy_type": h.strategy_type,
        "indicators_used": h.indicators_used,
        "params_tested": h.params_tested,
        "best_sharpe": h.best_sharpe,
        "invalidation_reason": h.invalidation_reason,
        "evidence_count": len(h.evidence),
        "evidence": [
            {
                "run_id": e.run_id,
                "iteration": e.iteration,
                "metric": e.metric,
                "value": e.value,
                "conclusion": e.conclusion,
                "reasoning": e.reasoning,
                "timestamp": e.timestamp,
                "source": e.source,
                "ref_id": e.ref_id,
            }
            for e in h.evidence
        ],
        "created_at": h.created_at,
        "updated_at": h.updated_at,
        "source": h.source,
    }


def serialize_artifact_summary(a: Any) -> dict[str, Any]:
    """Exactly routes_read.py's GET /artifacts list-item shape."""
    return {
        "artifact_id": a.artifact_id,
        "type": a.type,
        "name": a.name,
        "universe": a.universe,
        "status": a.status.value,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "initial_sharpe": a.initial_sharpe,
        "initial_max_dd": a.initial_max_dd,
        "deflated_sharpe": a.deflated_sharpe,
        "holdout_passed": a.holdout_passed,
        "stress_test_passed": a.stress_test_passed,
    }


def serialize_trade_plan_artifact(a: Any) -> dict[str, Any]:
    """Exactly routes_trade_plan.py's own `_artifact_to_dict` shape."""
    return {
        "artifact_id": a.artifact_id,
        "type": a.type,
        "name": a.name,
        "universe": a.universe,
        "status": a.status.value,
        "created_at": a.created_at,
        "updated_at": a.updated_at,
        "trade_plan_data": a.trade_plan_data,
    }
