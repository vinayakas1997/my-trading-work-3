# S-04: Two-Tier Memory With Relevance Ranking (Not a Flat 5-Row Dump)

## What It Is

Today's "memory" (P1, fixed for the self-reference bug by R-B) is one SQL query —
last 5 runs for this symbol, unranked, unfiltered by relevance, stringified
verbatim into every prompt (`llm_generator.py`'s `_build_memory_context`,
`service.py:96-108`). It's better than nothing, but it's not *memory* in any real
sense — it's a fixed-size recency window with no notion of "which past runs are
actually relevant to what I'm about to try."

Vibe-Trading splits this into two explicit tiers:

- **`WorkspaceMemory`** (`agent/src/agent/memory.py`) — ephemeral, single-run,
  just `run_dir` + counters, summarized for prompt injection. This is roughly
  what your per-run `history: list[IterationRecord]` already is.
- **`PersistentMemory`** (`agent/src/memory/persistent.py`) — cross-session,
  file-based, *typed* entries (`user/feedback/project/reference` —
  `persistent.py:29`), with a real relevance-ranking retrieval:
  `find_relevant()` (`persistent.py:238-263`) tokenizes the query and each memory
  entry, scores `metadata_hits*2.0 + body_hits*1.0`, sorts by score then recency,
  and returns only the **top-k** (3 in their usage) — not everything, not just the
  most recent.

It also bounds growth explicitly: `MAX_ENTRY_CHARS=8000` per entry with a
truncation marker, `MAX_INDEX_LINES=200` for the summary index
(`persistent.py:28,97`) — something your current "last 5 rows, dump as text"
approach doesn't need yet but will once a symbol accumulates dozens of runs.

## Why It's Required

"Last 5 runs" degrades badly for an actively-researched symbol: after 20 runs
across 4 different strategy families, the last 5 might all be one family (e.g. the
5 most recent momentum attempts), silently hiding the mean-reversion history that
would actually be relevant context for a new mean-reversion idea. Relevance
ranking (even simple token-overlap, not embeddings) fixes this by selecting *what
matters to this run*, not *what happened most recently regardless of topic*.

## Impact

- **If unfixed:** memory quality quietly degrades as research volume on a symbol
  grows — the exact opposite of what "the agent gets smarter over time" is
  supposed to mean.
- **If fixed:** memory context scales with actual relevance instead of recency,
  and stays bounded in size (no unbounded prompt growth as history accumulates).

## How to Use Effectively

1. Don't build a new memory subsystem from scratch — extend
   `get_past_run_summaries()` (`storage/sqlite_backend.py`) to fetch a larger pool
   (e.g. last 20, not last 5), then apply token-overlap scoring against
   `user_idea` client-side in `_build_memory_context()`, keeping only the top 5 by
   score+recency instead of just the most recent 5.
2. Once **S-01**'s hypothesis-matching score function exists, reuse the exact same
   scoring logic here — same problem (rank by relevance to `user_idea`), one
   utility function instead of two divergent implementations.
3. Add a size cap on the assembled `memory_context` string (mirror
   `MAX_ENTRY_CHARS`) — this protects against one pathological run (extremely long
   `user_idea` or many past runs) silently bloating every subsequent prompt.
4. This is a good candidate to combine with **S-02**: once evidence carries a
   `report_path`, memory entries can cite "see run #42's report for the full
   picture" instead of trying to cram everything into the summary string.

## Implementation Hint — Where This Fits Today

**Entry points:** `storage/sqlite_backend.py:124-137`
(`get_past_run_summaries()`) for the data pool, and `llm_generator.py`'s
`_build_memory_context()` (module-level function, called from `service.py:100-108`)
for the ranking/formatting.

**Why this is feasible right now:**
- `get_past_run_summaries(symbol, limit)` already returns `user_idea`,
  `best_sharpe`, `total_iterations`, `status`, `created_at` for every past run —
  exactly the fields a token-overlap score needs (`user_idea` vs the current run's
  `user_idea`). No new columns, no new query joins.
- R-B already fixed *when* this is queried (before `insert_run`,
  `service.py:96-108`) — this suggestion only changes *how many* rows are fetched
  (raise `limit` from 5 to ~20) and *how* they're filtered down to the final 5
  (score instead of raw recency), inside the same function.
- If **S-01**'s token-overlap scoring function gets built first, this is a direct
  reuse — same signature shape (`idea: str, candidate_text: str -> float`), same
  normalization helper. Build S-01 first and this becomes almost free.

**What NOT to do:** don't build a separate `PersistentMemory`/`WorkspaceMemory`
class hierarchy to mirror Vibe-Trading's exact two-tier design — your two tiers
already exist implicitly (`history: list[IterationRecord]` per-run vs SQLite
across-run), they just aren't named or separately reasoned about. Naming/
formalizing them isn't necessary to get the relevance-ranking benefit; the ranking
function is the part worth building.

## Potential Bugs to Watch For While Testing

- **Relevance ranking can silently drop the most recent run.** If the most recent
  run scores low on token overlap with the current `user_idea` (e.g. it was a
  different strategy family), pure relevance ranking excludes it entirely — but
  "what just happened last" can matter operationally even when it's not
  topically similar (e.g. "the last run crashed" or "the last run is still
  RUNNING"). Test whether you need a hybrid rule (always include the single most
  recent run + top-N by relevance) rather than pure relevance-only selection.
- **Zero-relevant-match fallback.** If `user_idea` is very short/generic and
  every past run scores 0, the memory context could end up empty even though 20+
  past runs exist and *some* general context would still help. Test this
  explicitly — decide and verify whether the fallback is "show the N most recent
  regardless of score" or "show nothing," since silently showing nothing when
  data exists is easy to miss in casual testing (looks identical to "no past
  runs exist at all").
- **Tokenizing idea strings with numbers/tickers.** Ideas like `"SMA 50/200
  crossover"` need `50`/`200` to survive normalization if they're meaningful for
  matching parameter-specific strategies — test that the tokenizer/normalizer
  doesn't strip digits the way `_normalize_suggestion_key` (S-11/R-E) deliberately
  does for a *different* purpose. Don't reuse that function here by accident;
  they have opposite requirements (one strips numbers on purpose, this one
  probably shouldn't).
- **Cost of fetching a larger pool.** Raising `limit` from 5 to ~20 in
  `get_past_run_summaries()` is cheap normally, but test against a symbol with
  hundreds of accumulated runs (a heavily-researched symbol) to confirm the
  client-side scoring loop doesn't add noticeable latency to every run's startup.
