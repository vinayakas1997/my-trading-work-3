# Enhancement 2: Make Walk-Forward an Actual Gate, and Correct for Multiple Comparisons

## Current State Score: 4/10 — good module, disconnected from the decision that matters

## The Core Problem

The research loop (`vinu_research/loop.py:100-197`) runs up to 5 iterations, each one: backtest → critique → add filters → backtest again, **on the exact same `from_date`/`to_date` window every time**. The stop/PASS/REFINE decision (`loop.py:164-190`) is made entirely from that same in-sample backtest. This is the textbook definition of fitting to the test set: every filter added in iteration N was chosen *because* it improved the metric being used to decide whether to stop, on the only data the strategy will ever be evaluated against.

Layered on top: when `generator_mode` is `hybrid` or `llm`, iteration 1 alone generates `n_candidates` (default 3, `config.py:68`) independent LLM strategies. Across up to 5 iterations that's up to **15 distinct hypotheses** evaluated against one dataset. With 15 independent draws, getting one with an in-sample Sharpe that looks good by chance alone is not a surprising result — it's close to expected. Nothing in the codebase corrects for this.

## What's Actually There (and why it's not enough)

`walk_forward.py` is genuinely well-built:
- `WindowSplitter.split()` (`walk_forward.py:32-75`) constructs non-overlapping train/test windows with an explicit `gap_days` embargo (`walk_forward.py:57`) between them — correct, leakage-aware mechanics, confirmed by `test_walk_forward.py:61-77`.
- It's imported and called from `loop.py:23-28`.

But:
1. **It's disabled by default.** `config.py:57`: `walk_forward_enabled: bool = False`. A user running the documented default command (`vinu-research run "..."`) never triggers it.
2. **Even when enabled, it runs after the decision is already made.** `loop.py:204-213` calls walk-forward validation *after* `best_result`/`best_iteration` has already been selected from the in-sample loop. It has no path back into the filter-generation or stop-condition logic — it's a report annex, not a gate.
3. **It's not actually out-of-sample relative to the filters.** The windows are cut from the *same* full date range the refinement loop already tuned filters against (`loop.py:100`'s `from_date`/`to_date`). A filter that was added because it improved the in-sample Sharpe will tend to also look better on sub-windows of that same range, because it was chosen using information from across the whole range (e.g., "3 drawdowns happened in the London session" is a fact about the whole period, baked into a filter, then "validated" on pieces of that same period).
4. **`aggregate_metrics` (`walk_forward.py:78-98`) reports medians only** — no dispersion (std/IQR across windows), no count of windows where the strategy lost money, no test for whether IS and OOS Sharpe are statistically distinguishable.
5. **The report shows it only if it ran.** `report.py:150`: `if walk_forward and walk_forward.has_walk_forward`. Default report (walk-forward off) presents in-sample numbers with no visual indication that they're in-sample.

`sharpe_p_value` (Lo/Bailey standard error formula, correctly implemented at `vinu-simulator/.../metrics.py:160-175`) has the same problem: it's surfaced as a critic *suggestion* (`loop.py:497-501`), never used to block a PASS verdict. No minimum-trade-count check exists anywhere despite `trade_count` already being on the result model (`models.py:78`) — a strategy that traded 4 times over a year can still get PASS-verdicted on a lucky Sharpe.

## What to Build

### 1. Reserve a true holdout before the loop starts — `loop.py`

Split the requested date range once, before iteration 1, into a research window (used for all in-loop backtesting/refinement) and a **held-out window the loop never sees**:

```python
# loop.py, near the top of run()
from vinu_research.walk_forward import WindowSplitter

def _split_research_and_holdout(from_date: str, to_date: str, holdout_frac: float = 0.2, gap_days: int = 5):
    """
    Carve off the trailing `holdout_frac` of the requested range as a true holdout.
    The refinement loop (iterations 1-N, filter generation, stop decision) only ever
    sees `research_from`..`research_to`. `holdout_from`..`holdout_to` is evaluated exactly
    once, after the loop has already picked a final strategy.
    """
    ...
    return research_from, research_to, holdout_from, holdout_to
```

This is a different and stronger guarantee than the existing `walk_forward.py` windows: those still live entirely inside the researched range. A true holdout, carved off *before* any filter is chosen and never touched by `_generate_filters`, is what actually answers "does this generalize."

### 2. Gate PASS on holdout performance, not just in-sample — `loop.py:164-190`

```python
if verdict == "PASS":
    holdout_result = await self._run_backtest(final_code, holdout_from, holdout_to)
    is_sharpe = best_result.metrics.sharpe
    oos_sharpe = holdout_result.metrics.sharpe
    degradation = (is_sharpe - oos_sharpe) / max(abs(is_sharpe), 1e-6)
    if oos_sharpe < 0 or degradation > 0.5:
        verdict = "REFINE"
        feedback.additional_suggestions.append(
            f"Holdout Sharpe ({oos_sharpe:.2f}) degraded {degradation:.0%} vs "
            f"in-sample ({is_sharpe:.2f}) — likely overfit, not approved for holdout gap this large."
        )
```

Report this in `report.py` unconditionally (not gated behind `walk_forward_enabled`), so every report — default settings included — shows an IS vs. holdout comparison.

### 3. Multiple-comparison correction on candidate selection

When `n_candidates > 1`, apply a penalty proportional to the number of independent draws before ranking (deflated Sharpe ratio, Bailey & López de Prado):

```python
def deflated_sharpe(sharpe: float, n_trials: int, n_obs: int, skew: float = 0.0, kurt: float = 3.0) -> float:
    """Penalizes a Sharpe ratio for having been the best of n_trials independent backtests."""
    ...
```

Use this — not raw Sharpe — as the ranking key in `comparison.py::rank_candidates` (see [04](04-benchmark-cagr-bug-and-dead-code.md) for why that function isn't even being called today) and as an input to the PASS rule threshold (rule 5 in `loop.py`'s `_rule_based_check`, currently a flat `Sharpe >= 1.5`).

### 4. Minimum trade count gate

```python
# _rule_based_check, new rule
if result.trade_count < MIN_TRADES_FOR_SIGNIFICANCE:  # e.g. 30
    verdict = "REFINE"  # never allow PASS on a thin sample, regardless of Sharpe
    suggestions.append(
        f"Only {result.trade_count} trades over the period — "
        f"insufficient sample to trust Sharpe={result.metrics.sharpe:.2f}"
    )
```

## Code Changes Summary

| File | Change | Description |
|---|---|---|
| `loop.py` | MODIFY | Carve holdout window before loop starts; gate PASS on holdout re-test; wire in trade-count minimum |
| `config.py` | MODIFY | `walk_forward_enabled` default → `True`; add `holdout_fraction` (default 0.2), `min_trades_for_pass` (default 30) |
| `walk_forward.py` | MODIFY | Add `deflated_sharpe()`; extend `aggregate_metrics` to report dispersion and IS/OOS gap, not just medians |
| `report.py:150` | MODIFY | Always render IS vs. holdout comparison, not only when `walk_forward_enabled` |
| `comparison.py` | MODIFY | Rank by deflated Sharpe when `n_candidates > 1` |
| `tests/test_walk_forward.py` | NEW | Test that a strategy overfit to synthetic in-sample noise fails the holdout gate |

## Complexity & Verdict

- **Difficulty:** Medium. The mechanics (`WindowSplitter`) already exist; this is about moving the decision point, not building new math (deflated Sharpe is the one new formula, well-documented in the literature).
- **Priority:** **P0, immediately after [01](01-lookahead-bias-critical-fix.md).** This is the difference between "research tool" and "overfitting generator with a nice UI."
- **Risk:** Low technically. The main risk is that far fewer strategies will reach PASS once holdout-gated — that's the system working correctly, not a regression.
- **Time estimate:** 4-6 days.
