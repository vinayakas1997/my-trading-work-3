# Track A: Context-Efficient Retrieval

## What Changed

### 1. `vinu-agent/vinu_agent/memory/unified_store.py`

**Scored search** (`scored_search` method): Combines FTS rank, recency, source importance weight, and stored score into a single composite score. Entries are returned sorted by this score (descending).

**`SOURCE_WEIGHTS`**: Maps source types to importance multipliers:
- `research`: 3.0 (highest — vinu-research findings are most valuable)
- `simulator`: 2.5
- `stock_price`: 2.0
- `agent`: 2.0
- `news`: 1.0

**`_compute_composite_score`**: Normalizes four signals into 0-1 range:
- Source weight (40%): from `SOURCE_WEIGHTS` dict
- Recency (30%): decays linearly from 1.0 (now) to 0.1 (365 days old)
- FTS rank (20%): inverted so better matches score higher
- Stored score (10%): the entry's explicit `score` field, normalized

**Dedup**: `scored_search` deduplicates by `(source, source_id)` — entries from the same source with the same source_id are treated as duplicates and the first (best-scored) is kept.

**`search` and `list_by_symbol`**: Both now delegate to `scored_search` with `dedup=True`.

### 2. `vinu-agent/vinu_agent/agent/context.py`

**Context budget** (`max_memory_tokens`, default 2000): The `ContextBuilder` now enforces a token budget for memory injection. Entries are pulled per symbol (up to 10 per symbol, pre-scored via `list_by_symbol`), and if the total exceeds the budget, lower-scored symbols/entries are dropped.

**`_estimate_tokens`**: Rough token counter (~4 chars per token). Used to track budget consumption.

**`build_messages`**: Now iterates symbols in extraction order, building memory blocks and deducting from the budget. When budget is exhausted, remaining symbols are skipped.
