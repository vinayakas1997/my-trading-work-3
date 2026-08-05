---
name: api-design
status: discussion-phase
purpose: the consistent, positional URL pattern for every vinu-* component's API — decided so that any endpoint is predictable without per-component documentation. Covers the full pattern, each segment's meaning, status codes, and the open items still unresolved.
---

# API Design — One Consistent URL Pattern Across All vinu Components

## The core principle

Every component exposes its data through the **same positional shape** —
segment position and naming never change between endpoints. Once the
pattern is learned once, every endpoint is predictable, whether it's
`vinu-news`, `vinu-stock-price`, or `vinu-initial-analysis`.

## The full pattern

```
/v1/stage1/{component}/{action}/{ticker}/{granularity}/{time-range}[/{method}][/{run-id}]
```

Each segment, in order:

| # | Segment | Meaning | Fixed/positional rule |
|---|---|---|---|
| 1 | `v1` | API version — tracks the contract changing over time | Always segment 1 |
| 2 | `stage1` | Project-stage marker — stage 1 (pre-analysis) vs. future stage 2/3 (`vinu-live`, `vinu-portfolio`, etc.) | Always segment 2, for fast visual recognition |
| 3 | `{component}` | The literal `vinu-*` component name — `vinu-news`, `vinu-stock-price`, `vinu-initial-analysis` (only components in current scope; `vinu-strategy`/`vinu-simulator`/`vinu-research`/`vinu-agent` are step 5, deferred) | Always segment 3 |
| 4 | `{action}` | `fetch` (read an existing computed result) or `trigger` (kick off a new run) | Always segment 4, right after component — this is deliberate: action is universal to every component call, so it gets the most stable position, immediately after the thing it applies to |
| 5 | `{ticker}` | Single ticker (`AAPL`) or comma-separated list (`AAPL,TSLA,JNJ`) for methods that need multiple tickers jointly (iTransformer, MOIRAI, FinMamba, the cross-attention+GCN fusion) | Always segment 5; cardinality (one vs. many) doesn't change the position |
| 6 | `{granularity}` | Bar resolution — `1min`, `5min`, `15min`, `1hr`, `4hr`, `1day` (matches Alpaca's actual supported bar timeframes, since Alpaca is the single data source) | Always segment 6 |
| 7 | `{time-range}` | `{start-time}_{end-time}`, **full timestamp precision** (not just dates) — e.g. `2022-01-01T00:00:00_2026-06-30T23:59:59` for the fixed quarterly window, or `2026-08-05T15:45:00_2026-08-05T16:00:00` for a rolling live-feed window (last 15 minutes). Same segment shape covers both historical and live access — no special `live` literal needed. | Always segment 7 |
| 8 | `{method}` | Only present for `vinu-initial-analysis` — the specific method/angle name, e.g. `kronos`, `event-type-classification`, `garch`. **Singular only** — unlike `{ticker}`, no comma-separated list; multiple methods means multiple calls | Present only where applicable; `vinu-news`/`vinu-stock-price` don't need a method selector |
| 9 | `{run-id}` | The unique ID assigned by `trigger` at the moment it's called, returned in the response body. Used to poll `fetch` for that **exact** run's status/result rather than doing a plain ticker/time-range lookup. | **Always last**, when present — the most specific, most granular identifier, so it's trivially extractable by position regardless of component/method |

## Worked examples

```
GET  /v1/stage1/vinu-news/fetch/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59
GET  /v1/stage1/vinu-stock-price/fetch/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59
POST /v1/stage1/vinu-stock-price/trigger/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59
GET  /v1/stage1/vinu-initial-analysis/fetch/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59/kronos
POST /v1/stage1/vinu-initial-analysis/trigger/AAPL,TSLA/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59/itransformer

# Live-feed example (Section 1 methods, e.g. event-type-classification) — same shape, just a recent rolling window:
GET  /v1/stage1/vinu-news/fetch/AAPL/15min/2026-08-05T15:45:00_2026-08-05T16:00:00/event-type-classification

# Trigger → poll flow, using {run-id} as the last segment:
POST /v1/stage1/vinu-initial-analysis/trigger/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59/kronos
  → 202 { "run_id": "run_8f3a2b", "status": "computing", "computed_at": null, "tier": "tier3", "data": null }

GET  /v1/stage1/vinu-initial-analysis/fetch/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59/kronos/run_8f3a2b
  → 202 { "run_id": "run_8f3a2b", "status": "computing", "computed_at": null, "tier": "tier3", "data": null }   # still going

GET  /v1/stage1/vinu-initial-analysis/fetch/AAPL/1hr/2022-01-01T00:00:00_2026-06-30T23:59:59/kronos/run_8f3a2b
  → 200 { "run_id": "run_8f3a2b", "status": "ok", "computed_at": "2026-08-05T16:04:12", "tier": "tier3", "data": {...} }
```

## Why `fetch` vs. `trigger` maps onto something already decided

This isn't a new concept — it's the API-level realization of
`../00-project-understanding/02-storage-plan.md`'s Tier 2 (scheduled
quarterly runs) vs. Tier 3 (triggered pre-analysis, fired when a new
strategy/analysis arrives). `fetch` reads an already-computed Tier 2/3
result; `trigger` kicks off a fresh Tier 3 run.

## Response envelope

Every response, regardless of component or method, is wrapped in the same
5-field envelope — only `data`'s shape varies per method (see each
method's "Output format" section in `01-present-considerations/`):

```json
{
  "run_id": "run_8f3a2b",
  "status": "ok" | "computing" | "not_found",
  "computed_at": "2026-08-05T16:04:12",
  "tier": "tier2" | "tier3",
  "data": { ... method-specific output, or null if not ok ... }
}
```

- **`run_id`** — the unique verification code. Assigned by `trigger` the
  moment it's called (before the computation even starts), so it exists
  from the very first response onward. Doubles as the `{run-id}` URL
  segment for polling. Makes every response traceable back to the exact
  Tier 2/3 run that produced it — the API-level realization of
  `02-storage-plan.md`'s traceability requirement ("the plan cited the
  Q2 run, not Q1").
- **`tier`** — which storage tier the result came from (`tier2` =
  scheduled quarterly, `tier3` = triggered) — lets a caller distinguish a
  clean quarterly-series result from a one-off triggered run.

## Status codes

- **`200`** — success, data returned (fetch found a result, or trigger
  completed synchronously)
- **`202`** — computing/in progress (trigger accepted but not done yet —
  relevant since a triggered run won't complete instantly)
- **`404`** — `fetch` found no computed result for that
  ticker/method/time-range. Not an error in the usual sense — it just
  means nobody has `trigger`ed that combination yet; `fetch` never
  auto-triggers on your behalf.

## Why this ordering (the reasoning, not just the result)

The most **universal** parameters sit closest to the root; the most
**component-specific** ones trail behind:

1. `v1`/`stage1` — apply to literally every call, regardless of component
2. `{component}` — picks which service
3. `{action}` — universal to every component (everything can be fetched
   or triggered), so it sits immediately after component, in a position
   that never shifts regardless of how many segments follow
4. `{ticker}`/`{granularity}`/`{time-range}` — apply to every component
   that has time-series data, but not to the API/stage/component
   selection itself
5. `{method}` — only meaningful for `vinu-initial-analysis`, so it's last

This ordering is why the earlier "action at the end" idea was rejected:
`vinu-initial-analysis` has one extra segment (`method`) that
`vinu-news`/`vinu-stock-price` don't, so an end-anchored action would sit
at a different segment number depending on the component. Action-right-
after-component fixes that.

## Resolved items

1. ~~**Live-feed / no-time-window case**~~ — **resolved**: `{time-range}`
   carries full timestamp precision (not just dates), so a live-feed
   request is just a very recent, possibly continuously-sliding
   `{start-time}_{end-time}` pair (e.g. the last 15 minutes) — the exact
   same segment shape as a historical quarterly request. No special
   `live` literal needed, and positional consistency is preserved for
   all 32 methods, not just the 23 that need a real historical window.
2. ~~**Fetch when nothing's been computed yet**~~ — **resolved**: `fetch`
   stays strictly read-only — it does **only** a fetch, never triggers a
   computation on the side. If no Tier 2/3 result exists yet for that
   ticker/method/time-range, `fetch` returns **`404`**. The caller must
   separately call `trigger` to produce the result. This keeps the two
   actions cleanly distinct — `fetch` never has a hidden side effect, and
   `trigger` is the only action that ever starts a computation.
3. ~~**Pagination**~~ — **resolved**: page size = **500** records per
   page. A large `1min`-granularity, multi-year `fetch` gets split into
   pages of 500 instead of one giant response.
4. ~~**Whether `{method}` can also be a list**~~ — **resolved**: no —
   `{method}` stays **singular, one method per call**, unlike `{ticker}`
   (which can be a comma-separated list). A request for multiple
   methods' results means multiple calls, one per method.
5. ~~**Response envelope consistency**~~ — **resolved**: see the
   "Response envelope" section above — a fixed 5-field wrapper
   (`run_id`, `status`, `computed_at`, `tier`, `data`) around every
   response, with `run_id` doubling as the unique verification code.

## Open items — not yet resolved

None currently — all items raised so far are resolved. Revisit this
section if a new gap surfaces during actual implementation.

## Related files

- `../limitations_and_other_info.md` — Alpaca-only (why `{granularity}`
  matches Alpaca's bar timeframes), fixed `2022-01-01` start + quarterly
  cadence (why `{time-range}` looks the way it does)
- `01-method-separation.md` — the two sections (`live-feed-compatible` vs.
  `time-period-only`) resolved by the `{time-range}` timestamp-precision
  fix above
- `../01-present-considerations/00-index.md` — the 32 methods' Input/Output
  format details that shaped the `data` field's variability in the
  response envelope
- `../../00-project-understanding/02-storage-plan.md` — Tier 2/3 (source of
  the `fetch`/`trigger` distinction and the `tier` field) and the
  traceability requirement `run_id` satisfies
