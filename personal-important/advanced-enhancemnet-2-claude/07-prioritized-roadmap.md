# Round 2 Roadmap: Sequencing and a Verifiable Definition of Done

## Why This Roadmap Looks Different From Round 1's

`advanced-enhancement/12-overall-upgrade-roadmap.md` sequenced work by *feature area* (validation → intelligence → scale → production) and measured progress by whether a module existed and had tests. That roadmap was followed reasonably faithfully — `walk_forward.py`, `benchmark.py`, `comparison.py`, `llm_generator.py` all exist and have their own passing tests today. And yet the audit behind this folder found the system is still producing unvalidated, overfit-prone results by default. **"Module exists and is unit-tested" was not a sufficient definition of done** — it left the actual decision path (loop.py's stop/PASS logic) untouched by the very modules meant to make it rigorous.

This roadmap sequences by **blast radius on trust in the numbers**, and each phase's "done" criterion is an end-to-end behavioral assertion (run the CLI, check the report), not a unit test passing in isolation.

## Phase 1: Make the Numbers Real (P0) — ~1 week

| # | Doc | What | Why first |
|---|---|---|---|
| 1 | [01](01-lookahead-bias-critical-fix.md) | Remove `bfill()` leak in `custom_sim.py`; shift execution to T+1 in `simulator.py` | Every other metric in the system is downstream of these numbers. Fixing this changes every existing backtest result, so it must land before anything else is tuned against those results. |
| 2 | [02](02-overfitting-and-walkforward-gating.md) | Carve a true holdout window before the loop starts; gate PASS on holdout re-test, not just in-sample; enable walk-forward by default | Without this, the loop's iteration count and candidate count directly drive overfitting risk — every subsequent efficiency or feature improvement (parallelizing candidates, more templates) makes this worse, not better, until it's gated. |

**Definition of done:** Run `vinu-research run "SMA crossover on AAPL" --from 2024-01-01 --to 2024-12-31` with default settings (no flags). The printed report must show a holdout/out-of-sample metrics section unconditionally (not only with `--llm` or a config flag), and a strategy whose filters were tuned to in-sample noise (verify with a synthetic adversarial test: construct a strategy that overfits a random-walk in-sample segment) must fail to reach PASS.

## Phase 2: Make the Numbers Honest (P1-P2) — ~1 week

| # | Doc | What |
|---|---|---|
| 3 | [03](03-cost-model-wiring-and-bugs.md) | Select `AlmgrenChrissCostModel` from config instead of hardcoded `FlatCostModel`; fix zero-volume-zero-impact bug; add risk-free rate; add short borrow cost |
| 4 | [04](04-benchmark-cagr-bug-and-dead-code.md) | Fix geometric-vs-arithmetic CAGR inconsistency in `benchmark.py`; wire `rank_candidates` into `loop.py` or delete it and correct the docs |
| 5 | [05](05-filter-generation-and-multi-comparison.md) | Replace substring-matched filter injection with typed, data-validated `FilterSuggestion` objects |

**Definition of done:** A backtest on a thin/illiquid symbol produces a visibly higher cost estimate than the same strategy on a liquid symbol (proving Almgren-Chriss is actually selected). `benchmark.py`'s CAGR and the top-level report's CAGR agree to the decimal on the same input series. Running the loop with a critique that happens to contain an incidental trigger substring does not inject an unrelated filter (regression test from [05](05-filter-generation-and-multi-comparison.md)).

## Phase 3: Make It Fast (P3) — 2-3 days

| # | Doc | What |
|---|---|---|
| 6 | [06](06-efficiency-performance.md) | Parallelize LLM candidate generation with `asyncio.gather` (after confirming `ResilientClient` concurrency safety); vectorize the simulator's per-day `.loc[date]` lookups into pre-extracted numpy arrays |

**Definition of done:** Wall-clock time for a `hybrid`-mode iteration-1 run with `n_candidates=3` drops from ~15-30s to ~5-10s. A backtest over a multi-year, multi-symbol range shows measurably lower per-call overhead in the simulator's inner loop (simple `time.perf_counter()` before/after comparison is sufficient evidence — no need for a formal benchmark suite for this).

## Sequencing Rationale (why not do efficiency first, since it's the fastest win)

Parallelizing LLM calls and vectorizing the simulator loop are the least risky, fastest changes in this whole folder — it would be tempting to do them first for quick visible wins. Resist that: Phase 1 is going to change how many backtests run per research call (holdout re-test, walk-forward windows), which changes the efficiency math itself — e.g., "batch independent backtests concurrently" ([06](06-efficiency-performance.md)'s item 3) only becomes meaningful once Phase 1 actually creates multiple independent backtests to batch. Doing efficiency work first means redoing part of it once Phase 1 lands.

## What "10/10" Should Mean Going Forward

Round 1's roadmap scored components by feature completeness (does a walk-forward module exist: yes/no). This round's finding is that the more useful question for a research tool is: **if you ran this system on pure random-walk noise with no real signal, would it correctly refuse to output a PASS-verdicted "profitable" strategy?** That's a test worth actually writing (`tests/test_no_signal_null_case.py`: feed the loop synthetic random-walk price data with a strategy idea, assert the final verdict is never PASS and the report flags the result as statistically indistinguishable from noise). Every phase above should be checked against that test before being called done — it's a stronger and more honest bar than "module exists, unit tests green," and it's the bar a real quant desk would actually hold this system to before letting it inform capital allocation.

## Effort Summary

| Phase | Focus | Time Estimate |
|---|---|---|
| Phase 1 | Look-ahead fix + overfitting gate | ~6-9 days |
| Phase 2 | Cost model, benchmark, filter correctness | ~6-8 days |
| Phase 3 | Efficiency | ~2-3 days |
| **Total** | | **~14-20 days (single developer)** |

This is smaller than round 1's ~48 man-days because almost everything needed already exists in the codebase — this round is a wiring and correctness pass, not new feature construction.
