"""MaturityAssessor -- vinu-research's own copy, wired into trade-plan
authoring's prompt. Design reference: missing-pieces-of-system/maturity-
agentic-system/00-maturity-agentic-system-explanation.md, step 3 of its
own "concrete next steps": "wire its output into trade-plan authoring's
prompt first (highest leverage, lowest risk -- it's the earliest
decision point)."

**Why a separate copy from vinu-reflection's
`vinu_reflection/reflection/_maturity_assessor.py`, not a shared
import**: that module reads vinu-agent's `PaperPerformanceStore` class
directly -- fine for vinu-reflection, which already mount-and-imports
vinu-agent as a whole service. vinu-research has no such dependency
(confirmed: `vinu-research/pyproject.toml` doesn't list vinu-agent at
all, while `vinu-agent/pyproject.toml` already lists vinu-research --
the one existing direction in this codebase). Importing vinu-agent from
here would be a genuinely new *reverse* dependency, circular at the
package level (`pip install -e` would need each package to install the
other first). Reads `paper_performance.db` via a minimal raw `sqlite3`
query instead, matching this session's own `_initial_analysis_parquet.py`
precedent for reading another service's on-disk data without installing
its package. The tier constants/logic below are intentionally duplicated
from vinu-reflection's module, not imported -- small, stable numbers,
not worth adding a new inter-service dependency to save ~15 lines.

**Real scope-down, colocation-dependent**: `calibration_entries` is
always reachable (vinu-research's own `strategy_store.db`, the same file
`author_trade_plan()`'s own `config.data_root` already points at).
`paper_performance` is vinu-agent's own store -- only reachable when
`config.agent_data_root` is set, which is only true on `agent-api` (the
container `author_trade_plan()` actually runs in for its real, primary
path -- see `vinu-agent/tools/trade_plan_tool.py`'s
`_author_and_freeze_trade_plan_in_process`). On `research-api` (the HTTP
fallback path only, `agent_data_root` intentionally left unset -- see
`docker-compose.yml`), `n_paper_trading_days`/`n_artifacts_with_paper_
history` fall back to 0, meaning `cold_start` and `paper_only` become
indistinguishable there. A real, honest, documented gap on the fallback
path only, not silently papered over -- the primary path (where this
matters most, matching "highest leverage, lowest risk" for the FIRST
wiring point) sees the real distinction.

`MATURE_MIN_REGIMES=2` is grounded the same way as vinu-reflection's
copy: `Artifact.regime_tag`'s real value set (`models.py`: "09 step2:
trend/range/high-vol") has exactly 3 members, so 2 of 3 is a majority,
not an arbitrary number. The mature-trade-count floor is NOT a fresh
constant here -- `assess()` takes it as a parameter so callers pass
`config.trade_score_calibration_min_sample` (default 30, env
`VINU_RESEARCH_TRADE_SCORE_CALIBRATION_MIN_SAMPLE`), the same real,
already-wired threshold `scheduled/executor.py`'s own calibration scan
uses -- literally the bar the design doc's own text names ("the minimum
sample size `trade_score_calibration.py` already requires"), and
respects an operator's own override automatically.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from vinu_research.storage.strategy_store import SqliteStrategyStore

MIN_PAPER_DAYS = 5
DEFAULT_MATURE_MIN_TRADES = 30
MATURE_MIN_REGIMES = 2

TIER_COLD_START = "cold_start"
TIER_PAPER_ONLY = "paper_only"
TIER_EARLY_LIVE = "early_live"
TIER_MATURE = "mature"


class MaturityAssessment:
    def __init__(
        self,
        *,
        tier: str,
        n_real_trades: int,
        n_paper_trading_days: int,
        directional_accuracy: float,
        regime_coverage: list[str],
    ) -> None:
        self.tier = tier
        self.n_real_trades = n_real_trades
        self.n_paper_trading_days = n_paper_trading_days
        self.directional_accuracy = directional_accuracy
        self.regime_coverage = regime_coverage

    def as_prompt_dict(self) -> dict:
        """The bounded subset of fields worth spending prompt tokens on --
        `directional_accuracy` rounded, everything else already small."""
        return {
            "tier": self.tier,
            "n_real_trades": self.n_real_trades,
            "n_paper_trading_days": self.n_paper_trading_days,
            "directional_accuracy": round(self.directional_accuracy, 3),
            "regime_coverage": self.regime_coverage,
        }


def _paper_history(agent_data_root: Optional[Path]) -> tuple[int, int]:
    """Raw sqlite3 read of vinu-agent's `paper_performance.db` -- see
    module docstring for why this isn't a `PaperPerformanceStore` import.
    Returns (total_paper_days, n_artifacts_with_real_paper_history).
    Fails open to (0, 0) on any missing file/row/parse issue -- this is a
    best-effort context addition to a prompt, never something that should
    raise and break trade-plan authoring."""
    if agent_data_root is None:
        return 0, 0
    db_path = Path(agent_data_root) / "paper_performance.db"
    if not db_path.exists():
        return 0, 0
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            rows = conn.execute("SELECT returns_json FROM paper_performance").fetchall()
        finally:
            conn.close()
    except sqlite3.Error:
        return 0, 0

    total_days = 0
    n_with_history = 0
    for (returns_json,) in rows:
        try:
            returns = json.loads(returns_json)
        except (TypeError, ValueError):
            continue
        if not isinstance(returns, list):
            continue
        total_days += len(returns)
        if len(returns) >= MIN_PAPER_DAYS:
            n_with_history += 1
    return total_days, n_with_history


def assess(
    strategy_store: SqliteStrategyStore,
    agent_data_root: Optional[Path],
    *,
    mature_min_trades: int = DEFAULT_MATURE_MIN_TRADES,
) -> MaturityAssessment:
    n_paper_trading_days, n_artifacts_with_paper_history = _paper_history(agent_data_root)

    n_real_trades = 0
    directional_correct_count = 0
    regimes: set[str] = set()
    for artifact in strategy_store.list_artifacts():
        entries = strategy_store.get_calibration_entries(artifact.artifact_id)
        if not entries:
            continue
        n_real_trades += len(entries)
        directional_correct_count += sum(1 for e in entries if e.directional_correct)
        if artifact.regime_tag:
            regimes.add(artifact.regime_tag)

    regime_coverage = sorted(regimes)
    directional_accuracy = directional_correct_count / n_real_trades if n_real_trades else 0.0

    if n_real_trades >= mature_min_trades and len(regime_coverage) >= MATURE_MIN_REGIMES:
        tier = TIER_MATURE
    elif n_real_trades > 0:
        tier = TIER_EARLY_LIVE
    elif n_artifacts_with_paper_history > 0:
        tier = TIER_PAPER_ONLY
    else:
        tier = TIER_COLD_START

    return MaturityAssessment(
        tier=tier,
        n_real_trades=n_real_trades,
        n_paper_trading_days=n_paper_trading_days,
        directional_accuracy=directional_accuracy,
        regime_coverage=regime_coverage,
    )
