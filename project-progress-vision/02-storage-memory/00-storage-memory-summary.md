# Vision: A Unified Storage & Agent-Memory Layer

## Why this exists

While designing [../01-vision-plan](../01-vision-plan/) (the 4-stage strategy-validation
pipeline), it became clear that `vinu-simulator`'s and `vinu-research`'s results storage is a
plain key-value store: write a row/file when a run finishes, nothing tracks what exists, what's
missing, or how fresh it is. Investigating what "good" looks like elsewhere in this codebase —
`vinu-stock-price` and `vinu-news` — found a genuinely strong design already proven in
production: a catalog/manifest, incrementally-updated watermarks, resumable job tracking, and
gap detection. That's the right pattern to bring to every other package's storage, including
the research/simulation pipeline and, ultimately, the agent's own memory of what it has learned.

But looking closely at *how* stock-price and news built that good design surfaced a real
inefficiency worth fixing at the same time: **both packages independently hand-rolled the same
catalog/watermark/dedup machinery from scratch**, instead of sharing it. There's a `vinu-lib`
package (`vinu-lib/sqlite.py`'s `SQLiteBackend`, `vinu-lib/parquet.py`'s `ParquetStore`) that
was clearly built to be exactly this shared abstraction — thread-safe WAL SQLite backend with
schema migrations, and a parquet store with built-in dedup-on-write — but grep across the whole
repo shows **it is used only in its own tests**. Neither `vinu-stock-price`'s `CatalogStore`
nor `vinu-news`'s `BackfillStore` imports or subclasses it. Two well-designed, independently
debugged, subtly-different implementations of the same pattern exist side by side, and neither
is `vinu-lib`'s.

## What's actually good (keep this)

- **`vinu-stock-price`**: `symbol_catalog` table (`vinu_stock/catalog/schema.sql`) tracking
  `first_bar_ts`/`last_bar_ts`/`archive_through`/`backfill_status`/`gap_count` per symbol;
  `backfill_jobs` table keyed `(symbol, year)`, idempotent via `INSERT OR IGNORE`; hot/cold tier
  data lifecycle (`live/` shards consolidated and rolled into immutable `archive/` year files);
  dedup-on-write keyed on `(symbol, provider, bar_ts)`; session-aware gap detection surfaced
  back into the catalog for follow-up.
- **`vinu-news`**: `backfill_status` table with an explicit `backfilled_up_to_ts` watermark
  updated **after every chunk**, not just at the end — so a crash mid-backfill resumes exactly
  where it left off; per-ticker pause/resume; permanent-failure marking instead of infinite
  retry loops; URL-level dedup plus semantic dedup via story-thread matching so near-duplicate
  articles merge instead of multiplying.

This is the reference design. The rest of the codebase — especially the research/simulation
pipeline from [01-vision-plan](../01-vision-plan/) — should look like this, not like a
key-value store.

## What's inefficient (fix this)

1. **Duplicated implementation.** The catalog/backfill/dedup logic exists twice, independently,
   with independent bugs and independent futures. A fix or improvement to one (e.g. better gap
   detection, a smarter dedup strategy) doesn't propagate to the other. Every *new* package that
   needs this pattern (the research/simulator storage from Phase 01 of this folder) is at risk of
   becoming a *third* independent reimplementation unless this gets consolidated first.
2. **`vinu-lib`'s `SQLiteBackend`/`ParquetStore` are dormant.** They exist, are tested in
   isolation, and appear to be a genuine match for the pattern both packages need — but nothing
   in the codebase actually depends on them. This is the highest-leverage fix: making them the
   real shared foundation retroactively de-duplicates two packages and gives every future
   package (research, simulator, and eventually the agent's own memory) a single proven base.
3. **No cross-package visibility.** Because each catalog is package-local (its own `meta.db`),
   there's no single place to ask "what data do we have, across price/news/research/simulation,
   for symbol X, and how fresh is it." Every consumer (including an LLM agent trying to decide
   what it already knows) has to query multiple services and reconstruct that picture itself,
   every time.

## The agentic-memory angle

This is the part that goes beyond "clean up the storage code" — it's the reason to invest in
this now rather than treat it as pure tech debt.

Every "memory" the trading system's LLM agents currently have is either (a) fully re-derived
each time (the risk critic recomputing metrics, `_characterize_stock` re-running a full LLM
call on a stock every single research run regardless of whether anything changed since last
time), or (b) stored as loosely-structured text an LLM has to re-read and re-interpret
(`report_md` markdown blobs, `HypothesisRegistry`'s flat JSON file, per-run LLM trace JSONL
files). None of this has a **freshness watermark** the way stock-price/news do — so there's no
cheap way for an agent to ask "is what I already know still current, or has enough changed that
I should re-derive it," short of just re-deriving it every time. That's wasted LLM calls, wasted
tokens, and — worse — an agent that can silently act on stale conclusions because nothing marks
them stale.

If the research/simulation pipeline (and eventually the agent's broader working memory) is
built on the same catalog+watermark pattern as stock-price/news, an agent's very first query
before doing *any* work becomes cheap and precise: "for symbol X, what strategies have we
already tried (catalog), how many trials total (lifetime trial count — this is also what
[phase-07 in 01-vision-plan](../01-vision-plan/phase-07-overfitting-and-robustness.md) needs),
when was this last validated (watermark — this is what
[phase-09](../01-vision-plan/phase-09-shadow-live-validation.md)'s decay detection needs), and
what's the compact structured summary of what we concluded (not a markdown blob to re-read, a
catalog row to look up)." That single query replaces re-scanning history, re-running
characterization LLM calls, and re-deriving conclusions — smaller prompts, fewer redundant LLM
calls, and a principled way to know when a conclusion is stale versus still trustworthy.

## Roadmap at a glance

| Phase | Delivers | Depends on |
|---|---|---|
| 1 | `vinu-lib`'s `SQLiteBackend`/`ParquetStore` become the real shared foundation; stock-price and news migrate onto it | — |
| 2 | Catalog + watermark + job-table pattern applied to `vinu-simulator`/`vinu-research` results storage | Phase 1 |
| 3 | Unified agent-memory layer: compact, queryable, freshness-stamped "what do we know" summaries spanning price/news/research | Phase 2 |
| 4 | Agent/skill/tool retrieval patterns updated to query the memory layer instead of re-deriving or re-scanning | Phase 3 |

See [01-plan-overview.md](01-plan-overview.md) for the full phased breakdown and dependency
detail, and the individual `phase-0N-*.md` files for what/impact/where/how-to-test.

Only this vision is being documented for now — no phase here is approved to start, consistent
with how [01-vision-plan](../01-vision-plan/) is being handled.
