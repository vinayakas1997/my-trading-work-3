# S-01: Hypothesis Identity — Search Instead of Substring Match

## What It Is

R-A fixed the worst version of the "one hypothesis per symbol" bug by requiring
`strategy_type` to match `user_idea` before reusing a hypothesis
(`loop.py:213-229`):

```python
def _normalize(s: str) -> str:
    return " ".join(s.lower().split())
norm_idea = _normalize(user_idea)
...
if norm_stored and (norm_idea == norm_stored or norm_idea in norm_stored or norm_stored in norm_idea):
    matched = h
```

This is a **substring match**, not real retrieval. It's a big improvement over
"most recently updated hypothesis for this symbol, regardless of strategy," but it
still has a sharp edge: substring containment is directional and unweighted, so a
short or generic `user_idea` can false-match an unrelated hypothesis. Example:
`user_idea = "trend"` will match a stored `strategy_type = "trend-following momentum
with ADX filter"` (since `"trend" in norm_stored`), even if the actual intent this
time is different (e.g. "trend reversal exhaustion play" — conceptually opposite,
but "trend" is still a substring).

Vibe-Trading doesn't have this problem because it doesn't do symbol-scoped
lookup-and-reuse at all. `HypothesisRegistry.search()`
(`Vibe-Trading/agent/src/hypotheses/registry.py:309-345`) does token-overlap
scoring across `title + thesis + universe + signal_definition + notes/links`,
returns ranked results, and lets the **caller** decide whether the top match is
close enough to reuse — it's a search-and-judge pattern, not an
implicit-key-and-reuse pattern.

## Why It's Required

The whole point of P1/P3 is "don't repeat past failures." If hypothesis identity
can still silently drift (a generic idea reusing an unrelated hypothesis's evidence
trail), you get the same failure mode R-A was meant to close, just with a higher
bar to trigger it — it'll show up rarely, be hard to reproduce, and corrupt
`best_sharpe`/`evidence` on a hypothesis that has nothing to do with the run that
touched it.

## Impact

- **If unfixed:** occasional silent hypothesis contamination, worse because it's
  now rare and easy to write off as a one-off rather than the systemic issue R-A
  was meant to close.
- **If fixed:** hypothesis matching becomes explainable ("matched because these N
  tokens overlapped with score S") and tunable (raise the match threshold if
  false-positives show up in practice), instead of a binary substring accident.

## How to Use Effectively

1. Replace the substring check with token-overlap scoring:
   ```python
   def _match_score(idea: str, stored: str) -> float:
       idea_tokens = set(_normalize(idea).split())
       stored_tokens = set(_normalize(stored).split())
       if not idea_tokens or not stored_tokens:
           return 0.0
       overlap = idea_tokens & stored_tokens
       return len(overlap) / min(len(idea_tokens), len(stored_tokens))
   ```
2. Require a minimum score (e.g. `>= 0.5`) before treating it as the same
   hypothesis; below that, create a new one. Log the score when matching so a
   wrong match is diagnosable from logs, not a mystery.
3. Don't over-engineer this into real embeddings/semantic search yet — Vibe-Trading
   itself only does token overlap, not vectors. Token-overlap with a threshold is
   the right amount of machinery for the current scale of this registry.
4. Pair with **S-02** (evidence-artifact-linking) — once evidence carries a
   `run_id`/`run_card_path`, a wrong match is at least traceable and reversible
   (you can see which run polluted which hypothesis and manually split them),
   which substring-matching today does not give you.

## Implementation Hint — Where This Fits Today

**Entry point:** `loop.py:212-229`, inside `StrategyResearchLoop.run()`. This is a
one-function change — replace the inline `_normalize`/substring-match block with a
scoring function; nothing outside this block needs to move.

**Why this is feasible right now, not blocked on anything:**
- `Hypothesis.strategy_type` (`models.py`) already exists and is already populated
  at creation (`self._current_hypothesis.strategy_type = user_idea`, right below
  the block you'd change) — the field this suggestion scores against is already
  there, R-A already put it in play.
- `HypothesisRegistry.query_by_symbol(symbol)` (`hypothesis_registry.py:214-222`)
  already returns every candidate hypothesis for the symbol — the registry needs
  **zero changes**; this is purely a selection-logic change in `loop.py` over data
  the registry already hands back.
- The `_normalize()` helper is already defined inline at the exact call site
  (`loop.py:216-217`) — you're extending an existing local helper, not introducing
  a new one from scratch.

**What a new agent should NOT do:** don't reach for embeddings or a vector store —
nothing else in this codebase uses them, and Vibe-Trading's own `search()` (the
thing this suggestion is modeled on) is plain token-overlap, not semantic search.
A `set()` intersection over `_normalize(s).split()` is the right scope.

## Potential Bugs to Watch For While Testing

- **Short-idea false positives via the `min(len)` denominator.** A score of
  `overlap / min(len(idea_tokens), len(stored_tokens))` gives a one-word idea like
  `"momentum"` a score of 1.0 against *any* stored `strategy_type` containing that
  word, even if the rest is unrelated. Test with deliberately short/generic ideas,
  not just realistic multi-word ones.
- **Threshold picked too high silently defeats the whole feature.** If the match
  threshold is too strict, genuinely-the-same strategy reworded differently
  ("SMA crossover" vs "moving average cross") never matches, so the registry
  quietly accumulates duplicate hypotheses forever instead of building history on
  one — this fails *silently* (no error, just degraded memory quality), so it
  needs an explicit test asserting a rephrased-but-equivalent idea *does* match,
  not just that an unrelated idea doesn't.
- **The existing broad `except Exception` swallows bugs in the new scoring
  function.** `loop.py:227-229` wraps the whole hypothesis block in `except
  Exception as e: LOG.warning(...)` — a bug introduced in the new scoring logic
  (e.g. a `KeyError` on a malformed stored record) will silently fall back to
  `self._current_hypothesis = None` rather than failing the test loudly. Test the
  scoring function in isolation, not only through the full `run()` path, so a
  regression can't hide behind that catch-all.
- **Cold-start path (`existing` is empty) must still work** — easy to break by
  only testing the "has candidates to score" branch.
