---
name: news-price-causality-quadratic-blowup
status: fixed
severity: never-finishes-for-a-realistic-article-volume
---

# Bug: `news_price_causality` rebuilt a full bar-timestamp index from scratch on every article, never finishing for AAPL/TSLA

## What was wrong

Triggering `POST /analysis/run/{ticker}` for all 3 tickers, AAPL and TSLA
(9,079 and ~11,000 real articles respectively, after the full 2022–2026
news backfill) got through 4 of 12 angles in seconds, then hung — CPU
pinned at 99.65%, memory at 98.96% of the container's 1 GiB limit — for
30+ minutes with zero progress, confirmed by directly querying the
`runs` table every 30s. JNJ (776 articles, ~12x fewer) finished normally.
This was not a hang/deadlock (confirmed via `docker stats`: CPU was
genuinely busy, not idle) — it was a real algorithmic blowup.

Root cause, found by reading the actual angle code
(`vinu-initial-analysis/vinu_initial_analysis/angles/news_price_causality/`):

- `compute.py`'s `time_format == "1min"` branch calls
  `compute_impact_for_article()` once per article — thousands of times per
  symbol — against the same 1-minute candle list (435,330 rows for AAPL
  over the 2022–2026 range) and the same SPY market-benchmark list every
  single time.
- `impact.py`'s `_compute_price_change()` rebuilds
  `ts = [c.get("bar_ts", 0) for c in candles]` — a full Python-level scan
  of the entire candle list — on **every call**, despite a comment
  claiming "bisect avoids full scans." It's called 5 times per article
  (once per impact window).
- `_helpers.py`'s `compute_abnormal_return()` has the identical pattern for
  its own `ts` index, plus (the bigger one) `_try_market_model()` calls
  `_compute_returns_series_indexed(market_candles)`, which **fully
  re-sorts** the entire SPY candle list (`sorted(candles, key=...)`, O(n
  log n)) from scratch, again on every single call.

None of these lists change across the per-article loop — they're built
once, upstream, in `compute.py`. Rebuilding/re-sorting them per article
turned an intended O(log n)-per-call design (the bisect usage) into an
O(articles × total_bars) blowup: confirmed to be genuinely unbounded in
practice for a several-thousand-article symbol over a 4.5-year, 1-minute
range.

## Why it mattered

This wasn't a slow-but-working angle — it was projected (see verification
below) to take on the order of 20+ minutes just for the impact-computation
portion alone, before the angle's other computations (Granger causality,
correlation, significance model) even ran, for any symbol with a realistic
multi-thousand-article news history. `end-to-end-test/02`'s own checklist
explicitly warns "this may take a while... don't assume a fast response,"
but this wasn't "a while" — it never finished within any reasonable test
budget, and would have blocked `03`, `04`, and `05` entirely for any
symbol with real news volume comparable to AAPL/TSLA.

## What was fixed

Precomputed the candle timestamp index and the market's indexed-returns
dict **once per symbol**, outside the per-article loop, and threaded them
through as optional parameters (backward-compatible — internal computation
still happens if omitted, so existing single-call tests/callers are
unaffected):

- `vinu_initial_analysis/angles/_helpers.py`: `compute_abnormal_return()`
  and `_try_market_model()` gained `candles_ts_index`/`market_returns_indexed`
  optional params, used in place of rebuilding when provided.
- `vinu_initial_analysis/angles/news_price_causality/impact.py`:
  `_compute_price_change()` gained `ts_index`; `compute_impact_for_article()`
  gained `ts_index_by_ticker`/`market_returns_indexed`, forwarding the
  per-ticker precomputed index down to both helper calls.
- `vinu_initial_analysis/angles/news_price_causality/compute.py`:
  precomputes `ts_index_by_ticker` and `market_returns_indexed` once,
  right after `candles_by_ticker`/`market_candles` are built, and passes
  them into every `compute_impact_for_article()` call in the per-article
  loop.

**Verification, not just a plausibility argument**: benchmarked directly
inside the container against the real production data (real AAPL 1-minute
candles + real AAPL articles, fetched live from `stock-api`/`news-api`):

| | 300 real articles | ms/article | projected full run (9,079 articles) |
|---|---|---|---|
| OLD (no precompute) | 40.34s | 134.5ms | ~1,221s (~20 min) |
| NEW (precomputed) | 0.13s | 0.4ms | ~4s |

**304.8x speedup**, same real data both times. Confirmed in production
immediately after: AAPL's re-triggered run completed all remaining 8
angles (including `news_price_causality`) in under 30 seconds total; TSLA
the same shortly after.

Existing test suite (`tests/test_impact.py`, plus the broader
`vinu-initial-analysis` suite) re-run before and after — no regressions;
the 11 pre-existing failures in `test_shock_clustering.py`/
`test_shock_personality.py` (`KeyError: 'bar_ts'`) are unrelated, confirmed
identical with the fix stashed out.

## What was achieved

`news_price_causality` — and by extension the whole
`POST /analysis/run/{ticker}` sweep — now actually completes for
symbols with realistic multi-thousand-article news histories, which is
every symbol this project's own reference ticker set (`AAPL`, `TSLA`)
already needed. Without this fix, `03`, `04`, and `05` of this checklist
would never have been reachable for 2 of the 3 tickers this whole e2e pass
exists to verify.
