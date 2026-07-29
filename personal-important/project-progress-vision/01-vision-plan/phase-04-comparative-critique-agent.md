# Phase 4 — Comparative Critique Agent (Stage 2)

Status: **not started** · Depends on: Phase 3, Phase 1 · Blocks: Phase 5 (comparison-angle surfacing), Phase 6

## What it is

Implements Stage 2 of the pipeline: a second agent that runs *after* a strategy has passed
Stage 1 refinement, and asks "would a different indicator, a different step, or an approach
tried in a prior run for this ticker have done better?" Unlike Stage 1's single PASS/REFINE/STOP
verdict, this stage's job is to produce **multiple distinct improvement angles** — each with its
own supporting evidence from the strategy's own history or a related prior strategy — as
something a human or a future iteration can act on, not a single forced answer.

This does not exist today. `comparison.py`'s `rank_candidates()` (in
`vinu-research/vinu_research/comparison.py`) is the closest existing building block, but it
only ranks *sibling* candidates generated within one generate/refine step of a *single* run
(scored by deflated Sharpe, drawdown penalty, win-rate bonus) — it has no concept of comparing
a finished strategy against other historical strategies for the same symbol, and it returns a
ranking, not a set of qualitative "here's what to try" angles.

## Impact

**Before this phase:** A strategy that reaches PASS in Stage 1 is promoted with no systematic
check against what's been tried before for the same ticker. Any insight about "we tried this
indicator six weeks ago and it helped" lives only in a human's memory or buried in old markdown
reports.

**After this phase:** Every strategy about to be promoted gets a structured set of comparison
angles, each traceable to specific supporting evidence (a specific prior iteration, a specific
metric delta). This becomes part of the permanent record for the strategy and feeds directly
into Stage 3's playbook as caveats/watch-items.

**What still won't work after this phase alone:** The playbook (Stage 3) doesn't yet surface
these angles to a trader — that wiring is Phase 5.

## Where changes occur

- `vinu-research/vinu_research/comparative_critic.py` (new module)
  - New dataclass `ComparisonAngle` (mirror `CriticFeedback` in `models.py`), fields:
    `angle_summary: str`, `suggested_change: str` (e.g. "swap RSI(14) for MACD-histogram
    crossover"), `supporting_evidence: dict` (references the specific prior
    iteration/run/artifact the comparison draws from), `estimated_impact: str | None`.
  - New class/function `ComparativeCritic.review(research_run_id: str) -> list[ComparisonAngle]`.
  - Inputs assembled for the LLM prompt: (a) the current refined strategy's code and full
    iteration history (from Phase 3's `research_iterations`), (b) a retrieved set of prior
    iterations/strategies for the same symbol — cheaply from `HypothesisRegistry`
    (`vinu-research/vinu_research/hypothesis_registry.py`, which already stores `Hypothesis` +
    one `Evidence` row per iteration with sharpe/max_dd/trade_count/conclusion) first, falling
    back to a raw `get_iterations_for_symbol` query (Phase 3) if needed, (c) prior
    promoted/approved strategies for the same symbol from `strategy_store.db`'s `Artifact`
    records (referenced by the existing approval flow, `service.py` lines ~229-260) — "attached
    strategies" in the user's terms.
  - Prompt responsibilities: for each retrieved comparison candidate, reason about *why* it
    differed (different indicator, different entry/exit logic, different regime handling) and
    *whether that difference would plausibly help the current strategy* — not just "candidate B
    had higher Sharpe" but "candidate B's ATR-based stop reduced drawdown in choppy regimes,
    current strategy lacks that." Output must be structured (`list[ComparisonAngle]`), not free
    text, so Stage 3 and any UI can iterate over it programmatically.

- `vinu-research/vinu_research/storage/sqlite_backend.py`
  - New table `research_comparisons`, one row per angle, keyed by `research_run_id`, so Stage 3
    (and any UI) can query "give me all surviving angles for this strategy" without re-running
    Stage 2.

- `vinu-research/vinu_research/service.py`
  - Trigger point: after Stage 1 reaches `PASS` (not on every `REFINE` iteration — this stage
    is comparative and expensive, meant only for a strategy about to be promoted), call
    `ComparativeCritic.review(...)` before the existing approval flow (`service.py` lines
    ~229-260) promotes the best iteration's code into `strategy_store.db`. Decide (and document
    the decision when implementing) whether Stage 2 is a hard precondition on approval or purely
    informational — the plan default is informational (angles are surfaced, not blocking),
    since the point is to suggest alternatives, not force a rewrite.

## How to test it

- Unit tests for `ComparativeCritic.review()` with a mocked LLM response and a seeded
  `research_iterations`/`HypothesisRegistry`/`strategy_store` fixture: confirm it returns a
  `list[ComparisonAngle]` (length > 1 in a case with multiple plausible prior candidates), and
  that each angle's `supporting_evidence` references a real prior iteration/run ID present in
  the fixture (not hallucinated).
- Test the "no prior history" case: a symbol with only this one run should still return
  gracefully (empty list or angles with `supporting_evidence: None`/general reasoning), not
  error.
- Storage round-trip test for `research_comparisons`: write angles, read them back for a given
  `research_run_id`, confirm field integrity.
- Integration test: seed two research runs for the same symbol with deliberately different
  strategy approaches (e.g. one MA-crossover, one RSI-based) in `research_iterations`, run
  `ComparativeCritic.review()` on the second, and assert the returned angles reference the
  first run's approach as a comparison point.
