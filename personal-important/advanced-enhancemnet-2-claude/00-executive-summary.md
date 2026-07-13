# Round 2 Audit: What's Actually Wired vs. What Round 1 Claimed to Build

## Context

`advanced-enhancement/` (round 1) proposed 12 enhancements and `advanced-enhancement/12-overall-upgrade-roadmap.md` claimed the codebase moved from 7.2/10 toward 8.0/10 after "Phase 1" (walk-forward, extended risk metrics, benchmark comparison) and 9.2/10 after "Phase 2" (strategy generator upgrade). The recent commits (`4f2d01af`, `9617fff4`) did land real code for most of Phase 1 and Phase 2: `walk_forward.py`, `benchmark.py`, `comparison.py`, `llm_generator.py`, 15 strategy templates, an LLM risk critic.

This round is a **code-level audit of what that landed code actually does**, not what the docstrings say it does. Two independent passes — one over `vinu-simulator`'s backtest engine, one over `vinu-research`'s refinement loop — read the real files line by line. The verdict: **the modules exist and are individually well-written, but the integration wiring that would make them actually prevent bad outcomes is missing or defaulted off.** This is the most dangerous kind of gap in a quant system, because the system *looks* rigorous (walk-forward module, p-value calc, benchmark alpha/beta) while the default code path is still exactly as overfit and leakage-prone as before Phase 1.

## Overall Score: 6/10 (not 8.0-9.2/10 as round 1's roadmap projected)

| Component | Round 1 claimed | Actual audited state | This round's docs |
|---|---|---|---|
| Look-ahead safety | N/A (not tracked) | **Broken** — `bfill()` leak in the LLM-generated-code execution path, same-bar signal/execution with no engine-level guard | [01](01-lookahead-bias-critical-fix.md) |
| Walk-forward validation | 4→10/10 | Module is correct in isolation, but **not in the decision path**; disabled by default; post-hoc annex only | [02](02-overfitting-and-walkforward-gating.md) |
| Overfitting controls | not addressed | Up to 15 hypotheses (3 candidates × 5 iterations) fit against one in-sample window, **zero multiple-comparison correction** | [02](02-overfitting-and-walkforward-gating.md) |
| Slippage/cost model | 7→10/10 (round 1 assumed baseline was already good) | `AlmgrenChrissCostModel` exists but **is never selected** — engine hardcodes `FlatCostModel`; missing volume silently zeroes out impact instead of penalizing it | [03](03-cost-model-wiring-and-bugs.md) |
| Benchmark comparison | 3→9/10 | Alpha/beta regression is correct, but CAGR is computed two different ways in the same module (geometric in one function, arithmetic-mean-compounded in another) | [04](04-benchmark-cagr-bug-and-dead-code.md) |
| Strategy generator ranking | 5→10/10 | `comparison.py`'s `rank_candidates`/`best_candidate` were built and tested but **`loop.py` never calls them** — it just takes `candidates[0]` | [04](04-benchmark-cagr-bug-and-dead-code.md) |
| Filter generation | not addressed | Still raw substring matching on critique text (`"cool" in text` matches unrelated words); can inject filters referencing synthetic default columns not present in real data | [05](05-filter-generation-and-multi-comparison.md) |
| Performance/efficiency | not addressed | LLM candidates generated sequentially (`await` in a `for` loop, no `asyncio.gather`); per-day Python loop in the simulator does repeated `.loc[date]` label lookups instead of pre-extracting to numpy | [06](06-efficiency-performance.md) |

## Why This Matters More Than It Looks

None of these are exotic bugs. Each one individually looks like a minor gap. Compounded, they mean: **the number a user sees at the end of a research run (e.g., "Sharpe: 0.72 → 1.22") is an in-sample, look-ahead-contaminated, multiple-comparison-inflated statistic, presented with the visual trust signal of a walk-forward module and a p-value calculator that aren't actually gating anything.** A strategy that "passes" this pipeline today has no more evidence behind it than one built by hand-tweaking parameters until the backtest looks good — the automation just makes that process faster and hides it behind more machinery.

The fix is not a rewrite. Every piece needed already exists in the codebase (`WindowSplitter`, `AlmgrenChrissCostModel`, `sharpe_p_value`, `rank_candidates`). This is a wiring problem, not a research problem — which is good news for cost of fixing it.

## Reading Order

1. [01-lookahead-bias-critical-fix.md](01-lookahead-bias-critical-fix.md) — **fix first, blocks everything else**. If prices leak backward, every other number is meaningless.
2. [02-overfitting-and-walkforward-gating.md](02-overfitting-and-walkforward-gating.md) — make walk-forward a gate, not an annex; add deflated Sharpe / multiple-comparison correction.
3. [03-cost-model-wiring-and-bugs.md](03-cost-model-wiring-and-bugs.md) — wire the cost model that's already been built; fix the zero-volume-zero-impact bug.
4. [04-benchmark-cagr-bug-and-dead-code.md](04-benchmark-cagr-bug-and-dead-code.md) — one-line CAGR fix, delete or wire `rank_candidates`.
5. [05-filter-generation-and-multi-comparison.md](05-filter-generation-and-multi-comparison.md) — replace keyword matching with structured, data-aware filter selection.
6. [06-efficiency-performance.md](06-efficiency-performance.md) — parallelize LLM candidate generation, vectorize the simulator's per-day loop.
7. [07-prioritized-roadmap.md](07-prioritized-roadmap.md) — sequencing, effort estimates, and a "definition of done" that's actually verifiable (not just "file exists").
