# Enhancement 11: Strategy Versioning & Evolution Tracking

## Current State Score: 4/10

The system produces a research report and saves the final strategy code, but **there's no versioning or evolution tracking**. Each research run starts fresh. If a strategy is refined, produced a version 1, then refined again later to produce version 2, there's no way to:
- See what changed between iterations
- Roll back to a previous version
- Compare version 1 vs version 2 performance over the same period
- Track which strategies are currently deployed (paper or live)

## Target State: 10/10

A complete strategy versioning system:
1. Every research run produces a versioned strategy with a unique ID
2. The version history shows every change (which filters were added, parameter changes, verdicts)
3. A/B testing compares any two versions over the same period
4. Deployed strategies are linked to their research run and version
5. A strategy registry provides a searchable catalog of all strategies ever created

## Why This Matters (The Problem)

- **No reproducibility**: If you run the same research twice, you get two different strategies (especially with LLM). There's no way to trace back which strategy was deployed.
- **No evolution tracking**: You can't see how a strategy evolved over time. "What made version 3 better than version 2?"
- **No rollback**: If the live paper trader has issues with version 5, you can't easily roll back to version 3 which was working fine.
- **No strategy catalog**: After 100 research runs, you have 100 `.py` files with no metadata, no search, no filtering.

## What to Build

### 1. Strategy Registry — New `vinu_strategy_registry`

An SQLite-backed registry that stores metadata for every strategy ever created:

```python
# vinu_research/storage/strategy_registry.py

@dataclass
class StrategyVersion:
    version_id: str              # UUID
    research_run_id: str         # Link to research run
    strategy_name: str           # User-provided or generated name
    symbol: str                  # Target symbol
    creation_date: datetime
    iteration: int               # Which iteration produced this version
    code: str                    # Full strategy code
    params: dict                 # Template parameters
    filters: list[str]           # What filters were applied
    sharpe: float                # Backtest Sharpe of this version
    max_dd: float                # Backtest MaxDD
    verdict: str                 # PASS, STOP, REFINE
    parent_version_id: str | None  # Previous version this evolved from
    description: str             # Human-readable description of changes
    deployed: bool               # Currently deployed to paper/live

class StrategyRegistry:
    def __init__(self, db_path: str = "strategies.db"):
        self._conn = sqlite3.connect(db_path)
        self._init_db()

    def _init_db(self):
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS strategies (
                version_id TEXT PRIMARY KEY,
                research_run_id TEXT,
                strategy_name TEXT,
                symbol TEXT,
                creation_date TIMESTAMP,
                iteration INTEGER,
                code TEXT,
                params TEXT,  -- JSON
                filters TEXT,  -- JSON
                sharpe REAL,
                max_dd REAL,
                verdict TEXT,
                parent_version_id TEXT,
                description TEXT,
                deployed INTEGER DEFAULT 0
            )
        """)
        self._conn.commit()

    def save_version(self, version: StrategyVersion):
        ...

    def get_version(self, version_id: str) -> StrategyVersion | None:
        ...

    def get_history(self, strategy_name: str) -> list[StrategyVersion]:
        """Get all versions of a strategy, ordered by creation date"""
        ...

    def get_deployed_strategies(self) -> list[StrategyVersion]:
        ...

    def search(self, query: str) -> list[StrategyVersion]:
        """Search by name, symbol, description"""
        ...
```

### 2. Research Run Tracking — New `vinu_research/models.py` addition

```python
@dataclass
class ResearchRun:
    run_id: str                    # UUID
    user_idea: str
    symbol: str
    from_date: str
    to_date: str
    config: dict                   # ResearchConfig as dict
    start_time: datetime
    end_time: datetime | None
    status: str                    # "running", "completed", "failed"
    iterations: int
    best_iteration: int
    best_sharpe: float
    best_max_dd: float
    report_md: str                 # Full report
    versions: list[str]            # version_ids of all strategies produced
```

### 3. Git-Like Version Diffs — Track What Changed

```python
class StrategyDiffer:
    def diff(self, v1: StrategyVersion, v2: StrategyVersion) -> str:
        """
        Produce a human-readable diff showing:
        - Which filters changed
        - Parameter differences
        - Performance changes
        """
        changes = []

        # Parameter diffs
        params_diff = self._dict_diff(v1.params, v2.params)
        if params_diff:
            changes.append(f"Parameters: {params_diff}")

        # Filter diffs
        v1_filters = set(v1.filters)
        v2_filters = set(v2.filters)
        added = v2_filters - v1_filters
        removed = v1_filters - v2_filters
        if added:
            changes.append(f"Added filters: {added}")
        if removed:
            changes.append(f"Removed filters: {removed}")

        # Performance diffs
        perf_parts = []
        if v2.sharpe != v1.sharpe:
            perf_parts.append(f"Sharpe {v1.sharpe:.2f} → {v2.sharpe:.2f}")
        if v2.max_dd != v1.max_dd:
            perf_parts.append(f"MaxDD {v1.max_dd:.1%} → {v2.max_dd:.1%}")
        if perf_parts:
            changes.append("Performance: " + ", ".join(perf_parts))

        return "\n".join(changes)
```

### 4. A/B Testing — Compare Versions Head-to-Head

```python
class StrategyABTest:
    """
    Run two strategy versions on the same out-of-sample period and compare.

    Usage:
        ab = StrategyABTest(research_tools)
        result = await ab.compare(
            version_a="v1_id",
            version_b="v2_id",
            test_period=("2024-07-01", "2024-12-31"),
        )
        # result.winner: "a", "b", or "tie"
        # result.confidence: statistical significance of the comparison
    """

    async def compare(
        self,
        version_a: str,
        version_b: str,
        test_period: tuple[str, str],
    ) -> ABTestResult:
        v1 = self.registry.get_version(version_a)
        v2 = self.registry.get_version(version_b)

        result_a = await self._backtest_version(v1, test_period)
        result_b = await self._backtest_version(v2, test_period)

        # Statistical comparison (Diebold-Mariano test for predictive accuracy)
        dm_stat, p_value = self._diebold_mariano_test(
            result_a.daily_returns, result_b.daily_returns
        )

        return ABTestResult(
            winner="a" if result_a.sharpe > result_b.sharpe else "b",
            version_a_sharpe=result_a.sharpe,
            version_b_sharpe=result_b.sharpe,
            dm_statistic=dm_stat,
            p_value=p_value,
            significant=p_value < 0.05,
        )
```

### 5. CLI Integration

```python
@vinu.cli()
def versioning():
    pass

@versioning.command()
@click.option("--run-id", required=True, help="Research run ID")
@click.option("--name", default=None, help="Strategy name")
def save(run_id, name):
    """Save the best strategy from a research run to the registry"""

@versioning.command()
@click.option("--strategy-name", required=True)
def history(strategy_name):
    """Show version history of a strategy"""

@versioning.command()
def list():
    """List all registered strategies"""

@versioning.command()
@click.option("--version-a", required=True)
@click.option("--version-b", required=True)
@click.option("--from", "from_date", required=True)
@click.option("--to", "to_date", required=True)
def compare(version_a, version_b, from_date, to_date):
    """A/B test two strategy versions"""
```

### 6. Report Enhancement

Add to the research report:

```markdown
=== VERSIONING ===
Strategy Name: sma_crossover_aapl_v3
Version ID: abc123-def456-ghi789
Run ID: run_2024_07_13_001
Parent Version: v2 (2 iterations ago)
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_research/storage/strategy_registry.py` | **NEW** | SQLite-backed strategy registry |
| `vinu_research/storage/__init__.py` | **NEW** | Storage module init |
| `vinu_research/models.py` | MODIFY | Add StrategyVersion, ResearchRun dataclasses |
| `vinu_research/loop.py` | MODIFY | Save version after each iteration, save run on completion |
| `vinu_research/cli.py` | MODIFY | Add save, history, list, compare commands |
| `vinu_research/report.py` | MODIFY | Add versioning section with run/version IDs |
| `tests/test_strategy_registry.py` | **NEW** | Tests for registry operations |
| `tests/test_ab_test.py` | **NEW** | Tests for A/B comparison |

## Complexity & Verdict

- **Difficulty**: Low (straightforward CRUD operations, SQLite-backed)
- **Lines of code**: ~400-600 total
- **Priority**: **LOW** — important for production but doesn't improve strategy quality directly
- **Dependencies**: None outside codebase
- **Risk**: Very Low — additive, doesn't change existing behavior
- **Time estimate**: 2-4 days

## Implementation Order

1. Build StrategyRegistry with SQLite backend
2. Add version saving to research loop (save every iteration)
3. Add CLI commands for history, list, compare
4. Add A/B test comparison
5. Add research run tracking
6. Write tests

## Data Model

```
strategy_registry.db
  └── strategies
       ├── version_id (PK)
       ├── research_run_id (FK → runs.run_id)
       ├── strategy_name
       ├── symbol
       ├── creation_date
       ├── iteration
       ├── code (TEXT — full strategy code)
       ├── params (JSON)
       ├── filters (JSON)
       ├── sharpe
       ├── max_dd
       ├── verdict
       ├── parent_version_id (self-referencing FK)
       ├── description
       └── deployed (bool)

research_runs
  ├── run_id (PK)
  ├── user_idea
  ├── symbol
  ├── from_date, to_date
  ├── config (JSON)
  ├── start_time, end_time
  ├── status
  ├── iterations
  ├── best_iteration
  ├── best_sharpe, best_max_dd
  └── report_md
```
