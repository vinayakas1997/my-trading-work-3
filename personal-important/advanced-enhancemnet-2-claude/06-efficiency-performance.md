# Enhancement 6: Efficiency — Parallelize LLM Calls, Vectorize the Simulator's Per-Day Loop

## Current State Score: 5/10 — correct but leaves easy wall-clock wins on the table

This doc is scoped to *speed*, separate from the correctness issues in [01](01-lookahead-bias-critical-fix.md)-[05](05-filter-generation-and-multi-comparison.md). Two concrete, verified inefficiencies, plus lower-priority ones worth tracking.

## 1. LLM candidate generation is sequential when it could be concurrent

`llm_generator.py:151-159`:

```python
for i in range(n_candidates):
    try:
        candidate = await self._generate_one(user_idea, symbol, from_date, to_date, indicators)
        if candidate is not None:
            candidates.append(candidate)
    except Exception as e:
        LOG.warning("LLM candidate %d generation failed: %s", i + 1, e)
```

Each `_generate_one` call is an HTTP round-trip to an LLM API that `how-it-works.md` §1 itself documents as taking 5-10 seconds. With the default `n_candidates=3`, generating candidates for iteration 1 takes **15-30 seconds sequentially** when the three calls have no data dependency on each other — candidate 2's prompt doesn't depend on candidate 1's response. Run concurrently, wall time drops to roughly one call's latency (~5-10s), a 2-3x reduction on the single slowest step of a hybrid/llm-mode run.

### Fix

```python
async def generate(self, user_idea, symbol, from_date, to_date, indicators=None, n_candidates=3):
    results = await asyncio.gather(
        *[self._generate_one(user_idea, symbol, from_date, to_date, indicators) for _ in range(n_candidates)],
        return_exceptions=True,
    )
    candidates = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            LOG.warning("LLM candidate %d generation failed: %s", i + 1, r)
        elif r is not None:
            candidates.append(r)
    return candidates
```

**Caveat — check before shipping:** `how-it-works.md` §1 states the system is gated by a `TokenBucket` rate limiter (10 requests/min) and a circuit breaker (3 failures → 30s open) inside `ResilientClient`. Confirm both are safe under concurrent callers — a `TokenBucket.wait_async()` implemented with a shared counter and proper locking is fine to call concurrently (that's its purpose); a circuit-breaker failure count that isn't atomic across concurrent tasks could over- or under-count failures. Audit `ResilientClient`'s internals for thread/task-safety before parallelizing call sites; if it isn't safe as-is, that's a small fix (an `asyncio.Lock` around the counters) that should land together with this change, not after.

## 2. Simulator's per-day loop does repeated pandas label lookups instead of vectorized numpy

`vinu_simulator/engine/simulator.py:98-109`:

```python
for step_idx, date in enumerate(total_calendar):
    prices = price_data.loc[date].values.astype(np.float64)
    volumes = (volume_data.loc[date].values.astype(np.float64) if volume_data is not None else None)
    ...
    target_weights = ws_aligned.loc[date].values.astype(np.float64)
```

Three `.loc[date]` label-based lookups happen on **every iteration of a Python-level loop over every trading day** in the backtest. `.loc` label lookups on a `DatetimeIndex` are not free — each one involves index hashing/binary search — and this cost is paid 3x per day, for every day, for every backtest the system runs (and per [02](02-overfitting-and-walkforward-gating.md), the system is about to run considerably *more* backtests per research run once holdout and walk-forward validation are wired in as gates rather than skipped by default).

### Fix

Extract each frame to a raw numpy array **once**, before the loop, and index by integer position instead of by date label inside the loop:

```python
price_arr = price_data.reindex(total_calendar).values.astype(np.float64)   # shape (n_days, n_symbols)
volume_arr = (
    volume_data.reindex(total_calendar).values.astype(np.float64)
    if volume_data is not None else None
)
weights_arr = ws_aligned.reindex(total_calendar).values.astype(np.float64)

for step_idx, date in enumerate(total_calendar):
    prices = price_arr[step_idx]
    volumes = volume_arr[step_idx] if volume_arr is not None else None
    target_weights = weights_arr[step_idx]
    ...
```

This is a mechanical change — the loop body's logic (rebalance decision, cost application, trade construction) is inherently sequential (each day's holdings depend on the previous day's), so it isn't a candidate for full vectorization without a larger rewrite. But replacing three repeated `.loc[date]` calls with three numpy array preallocations plus O(1) integer indexing removes the dominant per-iteration overhead cheaply, with no behavior change. Worth a quick before/after timing on a multi-year, multi-symbol backtest to confirm the magnitude (expect it to matter more as date range and symbol count grow — this is exactly the profile multi-asset research, proposed in round 1's `04-multi-asset-portfolio.md`, would have).

## 3. Lower-priority efficiency notes (not verified in depth, worth a look)

- **Story fetch caching** (`how-it-works.md` §8, Stage 4) already caches per symbol+date-range via `_LRUCache(max=64)` — good, no action needed, noted here so it isn't mistakenly "fixed" again.
- **SQLite risk-critic cache** exists (24h TTL) but only for the critic call, not the LLM generator call (`how-it-works.md` §3, Call Site 2: "Caching: None currently"). Given iteration 1 always regenerates candidates from scratch even when re-running the same idea/symbol/date-range (e.g. during iterative manual testing of the tool itself), adding a cache keyed the same way (SHA256 of prompt) would cut repeated-run latency and API cost during development/testing, at least.
- **Holdout/walk-forward backtests** ([02](02-overfitting-and-walkforward-gating.md)) will add more `POST /simulate/custom` calls per research run. If `vinu-simulator` calls aren't already parallelizable (multiple independent backtests — e.g. the N walk-forward windows — don't depend on each other), batch them with `asyncio.gather` the same way as candidate generation, rather than adding them as sequential extra stages.

## Code Changes Summary

| File | Change | Description |
|---|---|---|
| `llm_generator.py:151-159` | MODIFY | `asyncio.gather` for candidate generation instead of sequential `for`/`await` |
| `ResilientClient` (wherever defined, likely `llm.py`) | AUDIT/MODIFY | Confirm rate limiter + circuit breaker are safe under concurrent callers; add locking if not |
| `vinu_simulator/engine/simulator.py:98-109` | MODIFY | Pre-extract price/volume/weights to numpy arrays before the loop; index by position, not `.loc[date]` |
| `llm_generator.py` | NEW (optional) | SQLite cache for generator prompts, mirroring the existing risk-critic cache |
| `loop.py` (once [02](02-overfitting-and-walkforward-gating.md) lands) | MODIFY | Batch independent walk-forward-window/holdout backtests concurrently |
| `tests/test_llm_generator.py` | MODIFY | Update to assert candidates still come back correctly under concurrent generation (order may no longer match `n_candidates` submission order when using `return_exceptions=True` with `gather`) |

## Complexity & Verdict

- **Difficulty:** Low for both primary fixes — neither changes external behavior/results, only wall-clock time.
- **Priority:** **P3** — do after correctness fixes ([01](01-lookahead-bias-critical-fix.md)-[05](05-filter-generation-and-multi-comparison.md)), since [02](02-overfitting-and-walkforward-gating.md) alone will multiply the number of backtests per run, making the simulator loop fix and batched-backtest pattern more valuable once that lands.
- **Time estimate:** 1-2 days for both primary fixes; +1 day if adding the generator prompt cache.
