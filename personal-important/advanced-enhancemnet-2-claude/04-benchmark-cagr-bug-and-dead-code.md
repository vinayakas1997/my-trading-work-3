# Enhancement 4: Fix the Benchmark CAGR Inconsistency, Wire Up (or Delete) `rank_candidates`

## Current State Score: 5/10 — correct math undermined by one inconsistency, plus a whole module that isn't in the call graph

## Bug: Two Different CAGR Formulas in the Same Module

`benchmark.py` computes CAGR two different ways depending on which function you're in:

- `compute_benchmark_returns_metrics` (`benchmark.py:12-13`) uses proper **geometric** compounding: `(1 + total_return) ** (252 / n_days) - 1` (or equivalent cumulative-product form).
- `benchmark.py:82-83`, inside the alpha/beta/relative-metrics function, computes CAGR as:

```python
strat_cagr = (1 + mean_daily_return) ** 252 - 1
bench_cagr = (1 + mean_daily_return_bench) ** 252 - 1
```

Compounding the **arithmetic mean** daily return, rather than compounding the actual sequence of daily returns, ignores volatility drag (the mathematical fact that a series with the same mean but higher variance compounds to a lower actual ending value — e.g. +10%/-10% alternating gives a 0% mean but a -1% actual result over two periods). This systematically **overstates CAGR for volatile series** — which is disproportionately a problem for exactly the kind of single-stock, filter-laden strategies this system produces, since they tend to be higher-variance than the SPY benchmark they're compared against. It also means the "Excess CAGR" and "Alpha" figures reported side by side in the benchmark table (`how-it-works.md` §7) are internally inconsistent — one side of the comparison used geometric compounding, the other arithmetic.

### Fix

```python
# benchmark.py:82-83 — replace with the same geometric formula used at benchmark.py:12-13
def _geometric_cagr(daily_returns: pd.Series, periods_per_year: int = 252) -> float:
    cumulative = (1 + daily_returns).prod()
    n = len(daily_returns)
    if n == 0 or cumulative <= 0:
        return 0.0
    return cumulative ** (periods_per_year / n) - 1

strat_cagr = _geometric_cagr(strategy_daily_returns)
bench_cagr = _geometric_cagr(benchmark_daily_returns)
```

Extract this as a single shared helper and have *both* call sites in `benchmark.py` (and the duplicate implementation in `vinu-simulator/.../metrics.py:136-142` — the alpha/beta regression logic is duplicated between the two packages) import it, so there is exactly one CAGR formula in the codebase rather than three.

## Dead Code: `comparison.py::rank_candidates` / `best_candidate` Are Never Called

Round 1's `06-strategy-generator-upgrade.md` proposed a candidate-ranking system, and it got built — `comparison.py` has `rank_candidates()` (scoring by complexity penalty + backtest metrics, matching `how-it-works.md` §2's description of the flow: `"Rank → pick best candidate"`) and it's tested in `test_comparison.py`.

But `loop.py:403` — the actual point in the loop where a candidate is chosen — does:

```python
best_code = candidates[0].strategy_code
```

It takes the **first** LLM candidate returned, full stop. `rank_candidates` and `best_candidate` do not appear anywhere in `loop.py`'s call graph (confirmed by grep across the package). This means:
- The flow diagram in `how-it-works.md` §2 and §6, which shows `Rank → pick best candidate` as part of the pipeline, **does not describe what the code does.**
- Whatever ordering the LLM happens to return candidates in silently determines which strategy gets used — candidate 1 is not guaranteed to be, or even likely to be, the best of the 3.

### Fix

```python
# loop.py, wherever candidates: list[LlmCandidate] is produced
from vinu_research.comparison import rank_candidates

ranked = rank_candidates(candidates, backtest_results=None)  # rank on complexity alone pre-backtest, or...
best_code = ranked[0].strategy_code
```

If the intent (per `how-it-works.md` §2's `Rank["rank_candidates() score = 100 - complexity penalty + backtest metrics bonus"]`) is to rank using backtest results, that requires backtesting all `n_candidates` before picking one, not just the first — which is a bigger change (see [06](06-efficiency-performance.md) for parallelizing that). At minimum, wire in complexity-only ranking now; upgrade to backtest-informed ranking once candidate generation is parallelized.

If, after review, the team decides candidate ranking isn't worth the extra backtest calls, the honest fix is the opposite: **delete `rank_candidates`/`best_candidate` and correct the flow diagram** in `how-it-works.md` to show `candidates[0]` is used directly. Either fix is acceptable; leaving it as unreachable code that contradicts the documented architecture is not — the next person reading `how-it-works.md` will build on a false understanding of what selects the final strategy.

## Code Changes Summary

| File | Change | Description |
|---|---|---|
| `benchmark.py:82-83` | MODIFY | Replace arithmetic-mean CAGR with geometric CAGR helper |
| `benchmark.py` | MODIFY | Extract `_geometric_cagr()` shared by both call sites |
| `vinu-simulator/.../metrics.py:136-142` | MODIFY | Import the same shared CAGR helper instead of a duplicate implementation |
| `loop.py:403` | MODIFY | Call `rank_candidates()` before selecting `best_code`, or remove `comparison.py` and fix the docs |
| `how-it-works.md` §2, §6 | MODIFY | Update flow diagram once the actual behavior is decided |
| `tests/test_benchmark.py` | NEW | Regression test asserting `strat_cagr` matches geometric compounding on a synthetic volatile series (where arithmetic and geometric diverge measurably) |
| `tests/test_loop.py` | NEW | Test that with 3 mocked candidates of differing quality, the loop selects the ranked-best one, not `candidates[0]` |

## Complexity & Verdict

- **Difficulty:** Low. Both fixes are small, localized, and don't touch the engine's core numerical path.
- **Priority:** **P2** — real bugs, but lower blast radius than [01](01-lookahead-bias-critical-fix.md)/[02](02-overfitting-and-walkforward-gating.md). Worth doing in the same pass as [03](03-cost-model-wiring-and-bugs.md) since both are "finish wiring code that already exists."
- **Time estimate:** 1 day.
