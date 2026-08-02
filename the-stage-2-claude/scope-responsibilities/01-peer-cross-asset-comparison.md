---
name: peer-cross-asset-comparison
component: vinu-initial-analysis
status: not-started
---

# Item 1 — Peer / Cross-Asset Comparison

## What this is

Right now the only market-relative signal anywhere in the stack is the
single SPY market-factor used in `news_price_causality`'s abnormal-return
model (`vinu_initial_analysis/angles/_helpers.py::_try_market_model`).
There is no general "how is this ticker doing relative to its peers"
signal. This is a real, buildable gap — Alpaca already provides full
historical candle data for any peer ticker, same as it does for SPY, so
this is **not** blocked on a missing data source. It's a missing feature,
not a missing data feed.

## What already exists — don't duplicate it

`vinu_initial_analysis/angles/shock_clustering/compute.py` already builds
a multi-symbol universe (via `price_client.get_watchlist()`) and computes
pairwise correlation (`vinu_tools.compute.risk.covariance.
dynamic_covariance` / `correlation_from_covariance`) — **but only on
shock dates** (`_detect_shock_dates`), to answer "which symbols shock
together." That is a different question from "how correlated / how much
relative strength does this ticker have against peers, generally,
all the time." Read `shock_clustering/compute.py` in full before starting
— the universe-building and correlation-computation code there
(`_compute_shock_clusters`, lines 44-89) is directly reusable, just not
restricted to shock dates.

## Recommended approach

Two viable shapes — pick one, don't build both:

**Option A (recommended): new angle**, e.g.
`vinu_initial_analysis/angles/peer_relative_strength/`, following the
exact same folder contract every other angle uses (see
`vinu_initial_analysis/runner.py::AngleRunner._discover()` — any folder
under `angles/` with a `compute.py` and `spec.yaml` is auto-discovered,
no registration needed elsewhere):
- `compute.py` — signature must match the existing pattern: `compute(symbol, bars, news, from_ts, to_ts, time_format, price_client=None) -> pd.DataFrame`. Reuse `shock_clustering`'s universe-building logic (peer list from `price_client.get_watchlist()`), compute **rolling** correlation and relative-return (ticker return minus peer-basket average return) over the full requested range, not just at shock moments.
- `spec.yaml` — same shape as e.g. `angles/shock_clustering/spec.yaml`: `title`, `purpose`, `time_formats` (probably `1D` is enough — this is not an intraday-resolution question), `inputs`, `outputs`.
- Output columns should include at minimum: `symbol`, `peer_symbol`, `correlation` (rolling, e.g. 63-day window matching `shock_clustering`'s existing window default), `relative_return_20d` (or similar), `analysis_at`, `angle`.

**Option B: extend `shock_clustering`** to also emit a
non-shock-restricted correlation row (`type: "baseline_correlation"`
alongside the existing shock-date rows). Simpler (one file, no new
angle), but conflates two different questions (shock co-movement vs.
general relative strength) into one angle whose `purpose` field already
says something different. Not recommended unless there's a strong reason
to avoid a new angle folder.

## Files to touch (Option A)

- New: `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/compute.py`
- New: `vinu-components/vinu-initial-analysis/vinu_initial_analysis/angles/peer_relative_strength/spec.yaml`
- Reference only (don't modify): `vinu_initial_analysis/angles/shock_clustering/compute.py` (universe-building pattern), `vinu_initial_analysis/clients/price_client.py::get_watchlist` (line 35)
- Docs: add the new angle's output schema to `vinu-initial-analysis/docs/book/part-3-storage/ch16-schemas-models.md`, same pattern as the `ar_model`/`novelty_score`/`significance_score` entries already there.

## Expected output / how to verify

- `POST /analysis/run/{ticker}?angle_names=peer_relative_strength` (or
  whatever the folder gets named) returns `{"status": "completed",
  "row_count": N}` with `N > 0` for AAPL/TSLA/JNJ.
- `GET /analysis/angle/peer_relative_strength/AAPL` returns rows with
  sane correlation values (bounded [-1, 1], not NaN/constant across the
  whole series — a constant correlation for the entire history would
  indicate the rolling window isn't actually rolling).
- Spot-check against manual expectation: AAPL and another mega-cap tech
  peer should show meaningfully positive correlation; JNJ (defensive,
  low-beta, chosen in Stage 1 specifically to *break* the tech
  correlation — see `e2e-test-0731/full-plan.md`'s ticker table) should
  show visibly lower correlation to AAPL/TSLA than they show to each
  other. If JNJ doesn't look different, something is wrong with the
  computation, not with JNJ.
- Run for all three Stage 1 tickers (AAPL, TSLA, JNJ), sequentially not
  concurrently (see `full-plan.md`'s "How to verify" section).
