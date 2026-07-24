# Phase 3 — Unified Agent-Memory Layer

Status: **not started** · Depends on: Phase 2 · Blocks: Phase 4

## What it is

The first point where storage stops being purely package-local. Introduces a compact,
freshness-stamped, cross-package "what do we know" layer that an LLM agent (or any consumer)
can query in one place instead of separately hitting `vinu-stock-price`'s catalog,
`vinu-news`'s backfill status, and `vinu-research`'s catalog (Phase 2) and reconstructing the
picture itself every time.

Today, an agent's "memory" of prior work is scattered and un-stamped: `HypothesisRegistry`
(`vinu-research/vinu_research/hypothesis_registry.py`) is a flat JSON file with no freshness
concept; `report_md` markdown blobs require an LLM to re-read and re-interpret prose to extract
facts; per-run LLM trace JSONL files are an audit log, not a queryable summary; and nothing
connects "we have fresh news data for this ticker through yesterday" (news's catalog) with "we
last validated a strategy for this ticker 3 months ago" (research's catalog, Phase 2) — an
agent deciding whether to trust a conclusion has to know to check both, separately, and combine
them itself.

## Impact

**Before this phase:** Each package's catalog (Phase 2) is real and queryable, but there's no
single "memory" surface — an agent must know which package owns which fact and query each
independently. Cross-package staleness (e.g. "the strategy was validated on stale news data")
isn't visible unless someone thinks to cross-reference timestamps by hand.

**After this phase:** A single query — e.g. `get_memory_state(symbol="AAPL")` — returns a
compact structured summary: price data freshness, news backfill freshness, lifetime strategy
trial count, last validation timestamp and verdict, best known Sharpe, any comparison angles on
file (from [../01-vision-plan/phase-04-comparative-critique-agent.md](../01-vision-plan/phase-04-comparative-critique-agent.md)).
Each field carries its own watermark, so staleness is visible per-fact, not assumed.

**What still won't work after this phase alone:** Building the memory layer doesn't
automatically change how agents/skills/tools consume it — that behavioral change is
[phase-04](phase-04-context-efficient-retrieval.md). Phase 3 makes the query *possible*; Phase 4
makes it the *default path*.

## Where changes occur

- New module, likely `vinu-lib/memory.py` or a small new package (`vinu-memory`) so it can be a
  dependency of `vinu-agent`, `vinu-research`, and `vinu-strategy` without creating awkward
  cross-imports between sibling packages — decide the exact location at implementation time
  based on how `vinu-lib` is currently depended on across the tree.
- `MemoryQuery`/`get_memory_state(symbol: str) -> MemoryState` — a read-only aggregator that
  queries each package's Phase-2-style catalog (via whatever service/HTTP surface or, if
  colocated, direct SQLite read each package already exposes) and assembles one structured
  response. This should be a *read-time join*, not a duplicated copy of the data — the memory
  layer aggregates, it doesn't own new source-of-truth data.
- `MemoryState` fields, each with a value and a freshness timestamp: `price_data_through`,
  `news_data_through`, `lifetime_trial_count`, `last_validated_ts`, `last_validation_verdict`,
  `best_sharpe`, `open_comparison_angles` (count/summary), `known_failure_modes` (short list,
  derived from `HypothesisRegistry`/critic suggestion history rather than the full markdown
  report).
- `HypothesisRegistry` (`vinu-research/vinu_research/hypothesis_registry.py`) — extend or wrap
  so its conclusions are queryable through the same memory interface rather than only via direct
  file reads, and so its entries carry the same explicit freshness stamp as everything else in
  this layer.

## How to test it

- Unit test: seed synthetic catalog state across mocked stock-price/news/research catalogs
  (Phase 2), call `get_memory_state`, and confirm every field is populated with the correct
  value and freshness timestamp.
- Unit test: when one underlying catalog is missing data for a symbol (e.g. no news backfill
  started yet), confirm the corresponding `MemoryState` field degrades gracefully (explicit
  "unknown"/`None` with no timestamp) rather than erroring or silently defaulting to a
  misleading value.
- Staleness test: seed a case where research data is fresh but news data is 90 days stale, and
  confirm the aggregated response makes that visible per-field rather than an agent having to
  infer it.
- Round-trip test: confirm `get_memory_state` results match what a manual multi-query
  (hitting each package's Phase 2 catalog directly) would produce, for a handful of symbols with
  varied completeness.
