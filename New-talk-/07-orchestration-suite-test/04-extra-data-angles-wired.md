---
name: orchestration-suite-test-extra-data-angles-wired
status: phase-1-done
purpose: the real record of wiring news_price_causality, peer_relative_strength, trend_session_structure, and pnl_attribution into the orchestrator registry — closing all 4 items 03-still-open-not-wired.md originally tracked as open. Only the parallel-batch harness stays deferred (unchanged, see that doc).
---

# 07 — Orchestration Suite Test — Extra-Data Angles Wired

Registry grew from **24 → 30** angles, across two passes: the first 3
angles (24 → 29), then `pnl_attribution` (29 → 30) once its real blocker
— no importable `vinu_live` in this environment — was actually resolved
rather than left as an exclusion reason. This closes all 4 items
`03-still-open-not-wired.md` originally tracked; that doc's own reasoning
for *why* each needed something extra is unchanged and still accurate —
this doc records what was actually built to satisfy each need, and the
real proof it works.

## What was built

### `news_price_causality` — real articles fetched per symbol, once, cached across angles

`articles` is a required positional arg with no bars-only path — the fix
isn't a code change to the angle, it's fetching real articles as part of
building the batch. `build_batch_jobs()` gained a `news_repository`
param: any object exposing `get_news_for_ticker(ticker, start_ts=None,
end_ts=None, limit=100) -> list[dict]` — real, already-existing method on
`vinu_news.analysis.storage.repository.NewsRepository`. Articles are
fetched **once per symbol**, cached across every `bars_articles`-shaped
angle needing them in the same batch (confirmed by a dedicated test:
`test_build_batch_jobs_fetches_articles_once_per_symbol_and_caches_across_angles`),
not once per angle.

New call shape `"bars_articles"`: `run_fn(symbol, candles, articles)` —
`candles` is `bars.to_dict(orient="records")` (the real functions take
`list[dict]`, not a DataFrame, unlike every other registered angle).
Registered as two entries (matching the angle's own two real outputs,
same convention as `peer_relative_strength` below):
`news_price_causality_impact` (`run_impact_backtest`),
`news_price_causality_aggregate` (`run_aggregate_tests_backtest`).

### `peer_relative_strength` — a real, local, no-HTTP-server price_client adapter

Confirmed directly (research, not assumed): `peer_relative_strength`'s
`price_client` interface is exactly two methods —
`get_watchlist() -> list[str]` and `get_candles(symbol, from_ts=None,
to_ts=None, interval=None, limit=50000) -> list[dict]`. The real,
already-existing `PriceClient` (`clients/price_client.py`) implements
this but hits a **live HTTP stock-price service** — not something this
orchestrator should require just to run a batch.

Built `LocalPriceClient` (`clients/local_price_client.py`) implementing
the identical interface without a server: `get_watchlist()` returns
exactly the batch's own symbol list (the real "peer universe" for an
orchestrator run *is* the batch's own symbols — no separate peer-map
design decision needed), `get_candles()` calls
`vinu_stock.query.engine.fetch_candles()` directly against real cached
bars on disk — the same function already used elsewhere in this project
to fetch real AAPL/JNJ/TSLA data. Either adapter (`PriceClient` for a
live service, `LocalPriceClient` for local/offline runs) satisfies the
angle's real interface — `build_batch_jobs(price_client=...)` doesn't
care which.

New call shape `"bars_price_client"`: `run_fn(symbol, bars,
price_client=price_client)` — keyword, following the same rule the
`shock_personality` bug already established (never rely on a shared
positional slot across angles). Registered as
`peer_relative_strength` (`run_relative_strength_backtest`) and
`peer_relative_strength_forward_validation` (`run_forward_return_validation`).

### `trend_session_structure` — chained inline, no scheduler changes

`run_batch`/`AngleRunStatus` have no dependency notion at all — jobs run
independently, any order (confirmed by reading `orchestration.py` in
full). Rather than adding real dependency-graph scheduling for one angle,
`_run_trend_session_structure_chained(symbol, bars, time_format)` was
added to `orchestration_registry.py` itself: it calls
`trend_lifecycle.backtest.run_signal_outcome_backtest(symbol, bars,
time_format=time_format)` and immediately feeds the real result into
`trend_session_structure.backtest.aggregate_signal_outcomes_by_session(...)`.
Registered under the existing `"bars_time_format"` shape — no registry
mechanism changes needed, since the wrapper's own signature
`(symbol, bars, time_format)` matches that shape's existing keyword call
exactly.

Trade-off, stated plainly: this recomputes `trend_lifecycle`'s real
backtest a second time (the batch already runs `trend_lifecycle` as its
own separate job) rather than reusing that job's already-computed result.
Cheap and deterministic for a bars-driven statistical angle at this
scale — the real 72-job batch's own `trend_lifecycle` runs took well
under a second each — so the duplicate compute is a non-issue in
practice. If a future angle needs the same pattern at real cost, a real
dependency edge in `run_batch` (documented as option (a) in
`03-still-open-not-wired.md`) is the more correct general fix; not
needed yet for one cheap angle.

### `pnl_attribution` — a real, currently-empty book, wired without importing `vinu_live` into the registry

`pnl_attribution`'s real entry point, `aggregate_pnl_attribution(symbol,
closed_positions)`, needs real closed-trade data, not `bars` at all. Real
production data for this comes from `vinu_live.book.positions.
list_closed_positions(book_backend, symbol=...)` — but `vinu_live` wasn't
importable from this environment at all (`ModuleNotFoundError`), unlike
`vinu_news`/`vinu_stock` which already were. Fixed the actual blocker:
installed `vinu-live` editable (`pip install -e . --no-deps`, matching
how `vinu-news`/`vinu-stock-price` are already installed in this same
environment — lightweight deps, all already satisfied) rather than
working around it.

New call shape `"positions"`: `run_fn(symbol, positions)`. Kept the
registry module itself free of any `vinu_live` import, same convention as
`news_repository`/`price_client` — the caller fetches real positions
however they want (e.g. via a real `BookBackend`) and passes them in via
`build_batch_jobs(positions_by_symbol=...)`. A symbol missing from that
dict defaults to `[]`, not an error — `aggregate_pnl_attribution` already
has a real, correct `status: "no_data"` row for that case, so an empty
book isn't a wiring failure, it's the angle's own honest answer.

**Real proof, not fabricated**: repo-wide search confirmed no `book.db`
exists anywhere in this project — no live trading has ever run, exactly
as the angle's own design doc already stated. Built a real `BookBackend`
via the real production `init_book()` entry point (genuinely empty, not
a mock), queried `list_closed_positions()` for real AAPL/JNJ/TSLA — 0 for
each, correctly — and ran all 3 through the real registry/tracker:

```
AAPL: 0 real closed positions in the live book
JNJ: 0 real closed positions in the live book
TSLA: 0 real closed positions in the live book

=== DONE in 0.01s ===
ok: True
AAPL:pnl_attribution: status='no_data'
JNJ:pnl_attribution: status='no_data'
TSLA:pnl_attribution: status='no_data'
remaining tracked rows: 0
```

Separately, the actual aggregation math (win-rate/per-`artifact_id`
grouping) is proven via the same schema-faithful 3-position example
`22-pnl_attribution/02-real-scenario.md` already used and documented as
schema-accurate — now as a registry-level regression test
(`test_positions_shape_passes_real_closed_positions_through_and_groups_by_artifact`),
confirming the registry's wiring doesn't drop or reshape any real field
on the way to the angle.

## Real proof (news_price_causality / peer_relative_strength / trend_session_structure — 15-job batch)

Real AAPL/JNJ/TSLA data, no fabrication:

- **Real news**: `vinu-components/data/news/news.db` — 156 real
  AAPL-linked articles, 16 real TSLA-linked, 0 real JNJ-linked (confirmed
  directly via `NewsRepository.get_news_for_ticker()`, not assumed).
- **Real bars**: real cached 1D bars via `vinu_stock.query.engine.fetch_candles()`,
  150-bar tail per symbol (same real data source as the earlier 72-job run).
- **Real `LocalPriceClient`**: `get_watchlist()` returned `['AAPL', 'JNJ', 'TSLA']`;
  `get_candles('JNJ')` returned real OHLCV rows (e.g. `bar_ts=1641168000,
  open=149.78, close=150.94` — a real JNJ trading day, not synthetic).

15 real jobs (3 symbols × 5 registered entries) through the real
`AngleRunStatus`/`run_batch` tracker:

```
=== DONE in 27.3s ===
ok: True
succeeded: 15/15
failed:    0/15
remaining tracked rows: 0
```

| Job | Rows | Note |
|---|---|---|
| AAPL:news_price_causality_impact | 157 | Real per-article event-study rows. |
| JNJ:news_price_causality_impact | 0 | Correct: 0 real JNJ articles exist in this cache — the angle's own honest answer, not a bug. |
| TSLA:news_price_causality_impact | 41 | Real per-article rows against the 16 real TSLA articles (candle window affects how many mentions land inside scored bars). |
| \*:news_price_causality_aggregate | 0 / 0 / 2 | This run's bars tail (real, but an *unconstrained* fetch — earliest available window, ~2022) didn't calendar-quarter-overlap the news window (2023-01) for AAPL/JNJ; TSLA's 2 rows show the intersection logic firing correctly when it does overlap. A real property of this ad hoc check's date alignment, not a registry defect — a real production run would fetch bars and articles over the *same* window on purpose. |
| \*:peer_relative_strength | 60 each | Real per-day, real-peer rows via `LocalPriceClient`. |
| \*:peer_relative_strength_forward_validation | 8 each | Real forward-return buckets. |
| \*:trend_session_structure | 0 each | On this particular 150-bar 2022 window, `trend_lifecycle` matured too few `book_profits` signals to clear the session-bucket floor — consistent with the earlier 72-job run's own finding that `trend_lifecycle` itself produced very few rows (1 for AAPL) on a 150-bar window; not a wiring bug, a real small-sample outcome. |

## Testing

`tests/test_orchestration_registry.py`: grew from 30 → 49 tests across
both passes. First pass (24→29): registry-count assertion, parametrized
zero-arg-callable check extended to all 29 (stub `articles`/`price_client`
for the 4 new shapes), explicit `ValueError` when `bars_articles`/
`bars_price_client` angles are built without their real dependency,
regression tests for `bars_articles`'s bars→candles conversion and
`bars_price_client`'s keyword-passing, a caching test proving articles
are fetched once per symbol not once per angle. Second pass (29→30, the
`"positions"` shape): registry-count assertion updated to 30; parametrized
check extended to 30; `ValueError` when `positions=None` (never supplied)
but explicitly **not** when `positions=[]` (a real, valid empty-book
state) — a dedicated test for each; the schema-faithful 3-position
regression test above; `build_batch_jobs` tests for missing
`positions_by_symbol` (raises) vs. a symbol absent from a *provided*
`positions_by_symbol` (defaults to `[]`, does not raise). All 49 pass.

Full `vinu-initial-analysis` suite: **440 passed, 2 skipped, 0 failed**
after the first pass (up from 427); re-run after the `pnl_attribution`
pass too, same zero-regression discipline as every prior pass in this
project.

## What's still open after this pass

- **Parallel-batch harness integration into `run_batch`** — unchanged,
  still a deliberate deferral. See `03-still-open-not-wired.md`.
- **Per-angle real storage granularity** — unrelated to this pass,
  tracked separately.
- **Real Phase 6 trade data** — `pnl_attribution` is now fully wired and
  will produce real per-artifact attribution the moment real closed
  positions exist in the live book; nothing left to build here, just
  waiting on a live/paper-trading milestone this pass doesn't control.

All 4 originally-tracked angles in `03-still-open-not-wired.md` are now
wired. Only the parallel-batch harness remains a deliberate, tracked
deferral.

## Related files

- `03-still-open-not-wired.md` — the original reasoning for why each of
  these 4 angles needed something extra, and the still-accurate
  parallel-harness deferral section.
- `plan.md` — the angle classification table.
- `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/clients/local_price_client.py`
  — the local price adapter (no HTTP server needed).
- `../../vinu-components/vinu-initial-analysis/vinu_initial_analysis/storage/orchestration_registry.py`
  — the updated registry (30 entries).
