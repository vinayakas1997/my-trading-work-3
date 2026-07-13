# Enhancement 1: Walk-Forward Validation (Out-of-Sample Testing)

## Current State Score: 4/10

The system backtests on the **entire requested date range** in one pass. The same data is used to generate, refine, and evaluate the strategy. This is **overfitting by design** — every filter added by the risk critic is evaluated on the data it was derived from. The reported Sharpe/MaxDD metrics have no scientific validity for future performance.

## Target State: 10/10

A rigorous walk-forward framework that splits data into train/validation/test windows, optimizes on train, evaluates on validation, and reports out-of-sample metrics. The risk critic uses OOS performance to make refinement decisions, and the final report shows both in-sample and out-of-sample metrics with statistical confidence.

## Why This Matters (The Problem)

- **Overfitting**: Adding a London session filter that works in 2024 doesn't mean it'll work in 2025. Without OOS testing, every "improvement" could be fitting to noise.
- **No statistical confidence**: A Sharpe of 1.22 on one test means nothing. You need to see Sharpe distribution across multiple windows.
- **False sense of progress**: The risk critic sees MaxDD improve from -18.3% to -7.5% and declares victory. But if that improvement is noise, the real MaxDD in deployment could be worse than the original.
- **Academic standard violated**: Every serious quant paper reports in-sample AND out-of-sample metrics. Without this, the system produces non-credible results.

## What to Build

### 1. WalkForwardConfig — Configuration Dataclass

```python
@dataclass
class WalkForwardConfig:
    method: str = "expanding"       # "expanding" or "sliding"
    train_pct: float = 0.6          # 60% train
    val_pct: float = 0.2            # 20% validation
    test_pct: float = 0.2           # 20% test
    n_windows: int = 3              # Number of walk-forward windows
    min_train_days: int = 252       # Minimum 1 year of training data
    step_size_days: int = 63        # 3-month steps between windows
    gap_days: int = 5               # Gap between train and test to avoid leakage
```

### 2. Window Split Logic — New file `vinu_research/walk_forward.py`

```
Input: date range (from_date, to_date)
Output: list of Window objects, each with:
  - train_start, train_end
  - val_start, val_end (optional)
  - test_start, test_end
  - window_id (int)

Expanding method:
  Window 1: [2024-01-01 → 2024-06-30] train, [2024-07-01 → 2024-08-31] test
  Window 2: [2024-01-01 → 2024-09-30] train, [2024-10-01 → 2024-11-30] test
  Window 3: [2024-01-01 → 2024-12-31] train, [2025-01-01 → 2025-02-28] test

Sliding method:
  Window 1: [2024-01-01 → 2024-06-30] train, [2024-07-01 → 2024-08-31] test
  Window 2: [2024-04-01 → 2024-09-30] train, [2024-10-01 → 2024-11-30] test
  Window 3: [2024-07-01 → 2024-12-31] train, [2025-01-01 → 2025-02-28] test
```

### 3. Research Loop Integration — Modify `loop.py`

**Current flow:**
```
Full period → Generate → Backtest → Critic → Refine → Final on full period
```

**New flow:**
```
For each window in walk_forward_windows:
    Train on window.train → Generate → Backtest on train → Critic → Refine
    Validate on window.val → Backtest refined strategy → Store val metrics
    Test on window.test → Backtest best_val_strategy → Store test metrics

Final:
    Aggregate across windows
    Report: IS Sharpe, Val Sharpe, Test Sharpe, Sharpe gap
    = risk_critic checks gap > threshold → flags as unstable
```

### 4. Risk Critic Enhancement — The OSS Gap Check

Add these rules to `_rule_based_check()`:

```python
# Rule 7: Large gap between in-sample and out-of-sample performance
if has_walk_forward:
    sharpe_gap = is_sharpe - oos_sharpe
    if sharpe_gap > 0.5:
        suggestions.append(
            f"IS/OOS Sharpe gap {sharpe_gap:.2f} indicates overfitting — "
            f"simplify strategy or add regularization filter"
        )
    if oos_max_dd < -0.20:
        suggestions.append(
            f"Out-of-sample MaxDD {oos_max_dd:.1%} worse than IS — "
            f"add regime filter or reduce parameter count"
        )
```

### 5. Report Changes — Modify `report.py`

Add to the report output:

```markdown
=== OUT-OF-SAMPLE VALIDATION ===
Walk-forward windows: 3 (expanding)
Aggregation method: Median across windows

               | In-Sample | Out-of-Sample | Gap
Sharpe         | 1.22      | 0.78          | -0.44 ⚠️
Max Drawdown   | -7.5%     | -14.2%        | -6.7% ⚠️
Win Rate       | 59%       | 48%           | -11% ⚠️

Verdict: HIGH OVERFITTING RISK — Sharpe drop > 0.5
```

### 6. CLI Flags — Modify `cli.py`

```python
@click.option("--walk-forward", is_flag=True, help="Enable walk-forward validation")
@click.option("--wf-method", default="expanding", help="expanding or sliding")
@click.option("--wf-windows", default=3, help="Number of walk-forward windows")
```

## Code Changes Summary

| File | Change Type | Description |
|------|-------------|-------------|
| `vinu_research/walk_forward.py` | **NEW** | WalkForwardConfig, WindowSplitter, WalkForwardResult |
| `vinu_research/models.py` | MODIFY | Add WalkForwardRecord, OOSMetrics dataclasses |
| `vinu_research/loop.py` | MODIFY | Integrate walk-forward into research loop |
| `vinu_research/report.py` | MODIFY | Add OOS validation section to report |
| `vinu_research/config.py` | MODIFY | Add walk_forward config fields |
| `vinu_research/cli.py` | MODIFY | Add --walk-forward CLI flags |
| `vinu_research/tools.py` | MODIFY | Add fetch_benchmark method |
| `tests/test_walk_forward.py` | **NEW** | Unit tests for window splitting and OSS aggregation |

## Complexity & Verdict

- **Difficulty**: Medium (the window logic is straightforward, the risk critic changes are the hard part)
- **Lines of code**: ~400-500 total across all files
- **Priority**: **CRITICAL** — without this, the system's backtest results are not scientifically valid
- **Risk**: Low — walk-forward is additive, existing flow works unchanged without `--walk-forward` flag
- **Dependencies**: None outside existing codebase
- **Time estimate**: 3-5 days for a senior developer

## Implementation Order

1. Create `WalkForwardConfig` and `WindowSplitter` class (standalone, testable)
2. Modify `loop.py` to optionally use walk-forward windows
3. Modify `report.py` to show OOS metrics
4. Add risk critic rules for IS/OOS gap
5. Add CLI flags
6. Write tests
7. Validate on real data with known overfitted strategies
