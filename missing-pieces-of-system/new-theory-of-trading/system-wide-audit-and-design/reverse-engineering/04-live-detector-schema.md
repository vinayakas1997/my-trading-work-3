# Point 3 designed: the live indicator "detector"

**Status: design-only, nothing built.** Checked directly against real
code (2026-09-25) to ground this, not guessed — file/line citations
below.

## The key fact that makes this easy, confirmed against real code

`vinu-tools`' indicator library already computes over **whatever window
of rows it's given**, not only a full historical backfill series:

- `vinu_tools/compute/indicators/sma/sma.py:34` —
  `compute(rows: list[dict], *, name: str) -> dict[str, list[float | None]]`.
  Same signature confirmed on `rsi/rsi.py`. Every indicator module takes
  a plain `list[dict]` of bars and returns an array the same length,
  with `None` for the warmup period — there is nothing backfill-specific
  about this contract.
- `vinu_tools/compute/registry.py:330` —
  `warmup_bars_for_features(features)` **already exists** and already
  computes exactly how many trailing bars a given indicator/feature list
  needs (walks each module's own `warmup_for(name)`, e.g. `sma.py:21`'s
  `WARMUP_BARS = 100`). This removes the one thing that would otherwise
  need guessing: how many trailing bars a live fetch needs to fetch.
- `vinu-initial-analysis/vinu_initial_analysis/angles/signal_evidence/
  compute.py:414-484` — the real backfill angle builds `close`/`high`/
  `low`/`open`/`volume` as pandas Series from a `bars` DataFrame, then
  calls one private helper per indicator (`_sma_supporting`, `_adx`,
  `_rsi`, ...), each vectorized once over the whole DataFrame. **The
  live case is the same computation, just fed a shorter trailing window
  and reading only the last row instead of walking for historical
  crossings.**

**Conclusion**: point 3 needs no new indicator math and no new library.
It needs an orchestration function that (a) fetches a live trailing
window sized correctly via `warmup_bars_for_features`, (b) calls the
same computation the backfill angle already calls, (c) reads out only
the last row as "the current snapshot," instead of walking the whole
series for historical crossings.

## The one real risk: don't let live and backfill silently diverge

Track 2's engine design (`01-planning.md` Decision 16) already states
the principle this needs too: **"one shared implementation so historical
evidence and live detection can never silently drift apart."** Right
now, `signal_evidence/compute.py`'s per-indicator logic
(`_sma_supporting`, `_adx`, etc., lines ~155-390) is private to that
module, not a shared function. If the live detector reimplements its own
version of "call `vinu_tools`, assemble the 51-indicator dict" instead
of calling the exact same function backfill uses, that's a 5th instance
of the duplication pattern the parent audit already found four times
(item #21.2) — just one level higher up than raw indicator math this
time.

**Fix**: extract `signal_evidence/compute.py`'s per-indicator
supporting-snapshot assembly (the block building `sma_supporting`,
`ema_supporting`, `atr_14`, ... into one dict, roughly lines 441-484)
into a shared function — e.g.
`compute_supporting_snapshot(bars: pd.DataFrame) -> dict[str, Any]` —
living in `vinu_tools` (same home Track 2's engine uses, same reasoning:
called identically by backfill and live). Backfill calls it once per
historical trigger (already does the equivalent inline); the live
detector calls it once per candle-close event, on a short trailing
window, using only the returned last-row values.

## Do NOT reuse vinu-stock-price's own `?indicators=` param

`GET /candles/{symbol}` (`vinu-stock-price/vinu_stock/server/
routes_read.py:77-90`) accepts a `indicators` query param that computes
indicators server-side. **Checked and deliberately rejected as the live
data source for this**: the parent audit's item #19.3 already found
`vinu_stock/query/indicators.py` hand-rolls SMA/RSI/MACD/volatility/ADX
independently from `vinu-tools`, the same duplication-with-possible-
divergence bug found 4 times elsewhere in the audit series (item #21.2).
Using this endpoint's `indicators` param would silently pull in that
second, unverified implementation for live decisions while the backfill
side keeps using the correct one — exactly the kind of drift this whole
design series exists to eliminate. **Fetch raw candles only** (no
`indicators` param), compute via `vinu_tools` directly.

## The live-fetch contract

```
GET /candles/{symbol}?interval={timeframe}&limit={warmup_bars_for_features(needed)}
```

against `vinu-stock-price`, same route `vinu-live`'s existing
`scheduler.py::_fetch_prices` already calls for prices (confirmed real
precedent, same service, same route family — no new client needed,
extend the existing one). `needed` is the full 51-indicator list Track 1
already uses (`../../how-to-use-29th-angle/01-track1-how-it-works-
today.md`'s list), so this is one fixed warmup-bar count per timeframe,
computed once at startup, not per call.

**Field-name note, flagged rather than guessed**: the raw candle
response's timestamp field needs confirming at implementation time —
`vinu_stock/service.py:302` uses `"ts"` for the quote endpoint;
`signal_evidence/compute.py` expects a `bar_ts` column on its input
DataFrame. Whichever client builds the live DataFrame needs to map
whatever the real candles response calls it (likely `"ts"`) to
`bar_ts`, the same way the existing backfill price-fetch path already
must (not independently re-derived here — check that existing mapping
and reuse it, don't invent a second one).

## Output: what point 3 produces, per candle-close event

For a given `(ticker, strategy_id, timeframe, bar_ts)` event from the
poller (`03-poller-and-state-schema.md` Part A):

```
live_snapshot:
  ticker: str
  bar_ts: timestamp
  timeframe: str
  indicators: dict[str, float | None]   # the 51-value supporting snapshot,
                                          # same shape signal_evidence produces
  computed_at: timestamp                 # real wall-clock time this was computed,
                                          # per item #5's live_snapshots idea in
                                          # ../02-open-questions-strategy-and-simulation.md
```

This is exactly item #5's `live_snapshots` proposal from the parent
audit, now given a concrete producer (this point) instead of being an
abstract idea. Whether this gets persisted to its own table or passed
directly in-memory to point 4's state-tracker evaluation and point 5's
agent is an open call — leaning toward **persist it**, since
`staleness_seconds` (item #5's own proposal, computed at read time, not
stored) and the `strategy_stage_transitions` history table
(`03-poller-and-state-schema.md`) both benefit from being able to look
back at exactly what indicator values a past decision was made against,
not just the decision itself.

## What this deliberately leaves open

- Whether `compute_supporting_snapshot` needs the full 51-indicator set
  live, or only the subset a given strategy's must-condition/confirmation
  logic actually reads (fetching/computing fewer indicators live is
  cheaper per cycle) — Decision 12's "every workable indicator, not a
  curated subset" reasoning was for the *recording* layer; whether the
  same full-inclusion applies to a live, per-cycle, possibly-many-tickers
  hot path is a real cost/completeness tradeoff not resolved here.
- Exact persistence shape for `live_snapshots` (its own table vs. folded
  into `strategy_stage_transitions`) — not decided.
