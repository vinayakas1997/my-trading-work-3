---
name: 01-verification-pass
status: Done
phase: 0
code: V0
depends_on: []
unlocks: [03-gatekeepers-skill, 08-governor, 09-live-safety-doc]
---

# Step 01 — Verification Pass

## Why this step

Everything in this plan is built on claims about existing code. Most of
those claims were confirmed by directly reading the source — but four were
not, and this plan has already been burned once by trusting an assumption
that turned out wrong (e.g. `vinu-portfolio` was assumed stateless, then
turned out to already have circuit breakers and a drawdown scheduler; the
term "Monte Carlo" was assumed to mean parameter sweep, then turned out to
already mean something else in the code). Cheap fact-checking prevents
expensive rework later — a skill or tool built on a wrong assumption about
what `loop.py` already does, for instance, either duplicates it or fights it.

## What we're achieving

A short, direct-source-read answer to four specific open questions, so
downstream steps (03, 08, 09) can be written against confirmed fact instead
of inference. This step produces no code, no skill files — just verified
answers, written back into this file's "Findings" section.

## Where it matters in the future

Every later step that touches gatekeeping, the governor, or live safety
inherits whatever this step finds. If this step is skipped, those later
steps carry silent risk — they'll look complete but might duplicate or
contradict real behavior discovered too late (e.g. after A1/A2 are already
built around a wrong assumption).

## How it connects to other steps

- **Blocks nothing structurally** — Steps 02, 04, 05, 06 don't depend on
  this and can proceed in parallel with it.
- **Feeds 03 (gatekeepers skill)** — needs to know what
  `_build_risk_critic_prompt` in `vinu-research/vinu_research/llm.py`
  actually evaluates, so `gatekeepers` is written as a genuine complement to
  the existing risk-critic, not an accidental duplicate sitting beside it.
- **Feeds 08 (governor)** — needs to know `loop.py`'s actual stopping
  condition, so the governor document extends real behavior instead of
  re-describing or conflicting with it.
- **Feeds 09 (live-safety doc)** — needs `vinu-live` and
  `vinu_agent/server/routes_broker.py` read directly. The current claim
  ("OrderGuard halts via `/broker/halt`") came from a comment inside
  `vinu-portfolio/circuit_breakers.py`, not from reading either file. A
  doc meant to be the definitive live-safety reference should not be built
  on a comment in an unrelated file.

## Substeps

1. **Read `vinu-research/vinu_research/llm.py`, focused on
   `_build_risk_critic_prompt`.** Answer: what does the risk critic actually
   check (metrics? qualitative reasoning? both?), and does it produce a
   structured pass/fail, or freeform LLM text? Write the answer under
   Findings below.
2. **Read `vinu-research/vinu_research/loop.py` in full**, not just imports.
   Answer: what is the actual stop condition (max iterations only? also
   ties into `is_symbol_exhausted`? does it call the risk critic every
   iteration or only at the end?). Write the answer under Findings.
3. **Open `vinu-components/vinu-news`** — read its top-level structure and
   whatever computes news/shock signals. Answer: does it expose
   `news_price_causality` and shock-detection outputs the way Focus 2
   assumes, and how would an agent query them (API? stored table? both)?
4. **Open `vinu-components/vinu-live`**, plus
   `vinu-agent/vinu_agent/server/routes_broker.py`. Answer: does
   `/broker/halt` and `OrderGuard` actually exist as described, and what
   exactly triggers/reads the kill switch?
5. **Check `vinu-research/vinu_research/storage/sqlite_backend.py`'s schema**
   for an existing FTS5 (full-text search) table. Answer: does one already
   exist for hypothesis/reasoning text, or does Step 02 need to add it?
6. Record every answer in the Findings section below, each with the file
   and line range you read, so the next reader can jump straight to the
   source rather than re-deriving it.

## Findings

### 1. Risk critic — `llm.py::_build_risk_critic_prompt` (llm.py:32-96)

This function is **only a prompt formatter** — it assembles backtest
metrics, cross-run catalog history, rule-based suggestions, and
story/angle context into a text block for an LLM call. It evaluates
nothing itself.

The actual risk critic is `loop.py::_default_risk_critic`
(loop.py:1622-1659), which combines three layers:
1. `_cross_run_comparison()` — can force an immediate `STOP` verdict on
   its own.
2. `_rule_based_check()` (loop.py:1336-1418) — deterministic, hard-coded
   thresholds that generate *suggestions*: max_drawdown < -15%, Sharpe <
   0.5, win_rate < 40%, CVaR₉₅ < -3%, recovery_time > 120 days, annual
   turnover > 2000%, Sharpe p-value > 0.05. Angle context
   (`trend_lifecycle`, `news_causality`, `session_structure`) also feeds
   suggestions here — explicitly commented as "suggestions only — never
   changes verdicts" (loop.py:1362).
3. `_llm_enhanced_check()` — sends `_build_risk_critic_prompt`'s text to
   the LLM; its output can only **upgrade** a `REFINE` verdict to
   `PASS`/`STOP` via `_merge_feedback()` (loop.py:1554-1576), never
   downgrade one.

**Implication for Step 03:** the real gatekeeper logic already in
production is `_rule_based_check` + `_llm_enhanced_check`, with a
specific, deliberate asymmetry (LLM can escalate, never de-escalate; angle
context never changes a verdict). The `gatekeepers` skill should describe
*this* mechanism, with its real thresholds, not the placeholder metric
names originally drafted in `project-understanding/skills/gatekeepers/rules.yaml`.

### 2. Loop stop condition — `loop.py` (full read, 1770 lines)

The `for iteration in range(1, max_iterations + 1)` loop (loop.py:290-535)
has these stop paths, in the order they can trigger:
- **Hard cap:** `max_iterations` (config) bounds the loop itself.
- **Optional hard budget:** `_check_goal_budget()` (loop.py:1537-1549) —
  only active if a `Goal` object is passed into `run()`; checks
  `llm_calls_budget` and `time_budget_seconds`.
- Backtest returns `None` → break.
- Validation gate fails on the first iteration → break.
- **Meta-reflection pivot/stop:** when `iteration >= 2` and Sharpe < 0.1
  and trades < 5, `_reflect()` makes an LLM judgment call returning
  `pivot` / `stop` / `continue` — this is already a qualitative,
  reasoning-based continuation decision, not a formula.
- `verdict == "PASS"` and holdout check passes → break (success path).
- `verdict == "STOP"` → break.
- MaxDD exceeds `config.max_drawdown_threshold` → break.
- **`_is_improving()`** (loop.py:934-939) — breaks if `iteration >= 2` and
  the current Sharpe didn't beat the previous Sharpe by more than
  `config.improvement_threshold`. **This is already the "progress
  heuristic" Step 08 planned to add** — but it's a single-round check
  (this iteration vs. the last one), not an N-round-flat check.

**Checkpointing is write-only today:** `self._storage.save_checkpoint()`
is called every iteration (loop.py:461-468) when storage + `run_id` are
set, but nothing in `loop.py` ever calls `get_last_checkpoint()` or
otherwise resumes a `run()` call from a saved iteration — confirmed by
grepping the whole file for `resume`/`checkpoint`. Resumability across
sessions does not exist at this layer.

**No expectancy-style heuristic** (`EV = win_rate × avg_win − loss_rate ×
avg_loss`) exists anywhere in this file — confirmed genuinely new, as
Step 08 assumed.

**Implication for Step 08:** don't build a new progress heuristic — extend
`_is_improving()` (e.g. to an N-round window) and document the
relationship explicitly. Layer 1's resumability claim is not yet true
anywhere — it must be built (most naturally as an orchestration-level
concern in Step 02/08: read `get_last_checkpoint()` before starting a
`run()`, pass its state back in), not assumed to already exist.

### 3. News angle exposure — `vinu-news`

A full, mature pipeline, larger than assumed: RSS ingestion →
LLM enrichment (sentiment, threat, priority, category, ticker
extraction/dominance, price_reaction) → post-enrichment (cosine dedup,
NER, lead-pick, synonym normalization) → storage (sqlite/postgres
backends, plus its **own** FTS index at
`vinu_news/analysis/storage/fts.py` — separate from, and not reusable by,
`vinu-research`'s storage).

Read-only HTTP routes exist (`vinu_news/server/routes_read.py`):
`/latest`, `/ticker/{symbol}`, `/watchlist/news`, `/search`, `/poll/status`.
An agent can query these directly by ticker/date/provider/tier.

The `news_causality` signal already flowing into `loop.py`'s
`story["angles"]` comes from **vinu-initial-analysis's** angle
computation, not directly from these routes.

**Implication for Step 02:** decide whether the agent tool layer should
also query vinu-news's `/ticker/{symbol}` or `/search` directly for raw
articles (headline-level detail), in addition to the already-flowing
pre-computed angle summary — these are two different granularities of the
same underlying signal.

### 4. Live kill switch — `vinu-live`, `routes_broker.py`

**Confirmed accurate, not secondhand.**
`vinu_agent/vinu_agent/server/routes_broker.py` (full file read) implements
`/broker/halt`, `/broker/resume`, `/broker/status` on top of
`broker/kill_switch.py`'s `halt_trading` / `is_trading_halted` /
`resume_trading`, plus `/broker/order`, which the file's own docstring
(lines 101-107) states deliberately reuses the exact same `OrderGuard`
checks (kill switch, mandate limits, artifact gate, market hours) used by
the LLM's own order tool — so no caller, including `vinu-live`'s
scheduler, can bypass the safety layer through a second code path.
`vinu-portfolio/circuit_breakers.py`'s original claim about this is accurate.

**New finding, not previously known:** `vinu-live` is a full live-trading
operations layer, not a thin shell — `breaker/` (its own local circuit
breaker: `limits.py`, `engine.py`), `book/` (position tracking),
`trade_plan/` (orchestrator, condition evaluator, live metrics),
`feedback_loop.py` (writes realized trade outcomes back into research
calibration state), `scheduler.py` (`LiveScheduler.cycle()` — the actual
portfolio-execution loop), and `shadow_evaluator.py`.

**`shadow_evaluator.py` directly affects Step 09's premise.** It defines a
real, functional `ShadowEvaluator` class that fetches `BENCHING` artifacts
from vinu-research, computes paper-trading Sharpe from
`agent-api`'s `/broker/performance/{artifact_id}`, and automatically
promotes `BENCHING` → `ACTIVE` when paper performance holds up
(degradation ≤ 0.5, minimum 5 days of paper data) by calling
`/artifacts/{id}/promote`. This is exactly the shadow/paper-account gate
`promotion.py`'s docstring says doesn't exist.

However: grepping `ShadowEvaluator`/`shadow_evaluator` across every
`vinu-*` service shows it is referenced **only** inside its own file, plus
one comment in `feedback_loop.py`. Nothing calls `evaluate_all()` — not
`scheduler.py`'s `LiveScheduler.cycle()`, not `cli.py`, not any route in
`server/app.py`. **The class is real and working, but it is not wired into
any scheduled or running process — it is dead code today, not missing
code.**

**Implication for Step 09:** the gap is materially smaller than "no
shadow account exists" — it's "the shadow-account gate is built but never
runs." The document should say precisely that, and note that closing the
gap may be a wiring task (call `evaluate_all()` on a schedule) rather than
a design-and-build task.

### 5. FTS5 in `sqlite_backend.py`

**Confirmed absent.** Grepped
`vinu-research/vinu_research/storage/sqlite_backend.py` for
`fts5|FTS5|fts4|virtual table` (case-insensitive) — zero matches. No FTS
mechanism exists in `ResearchStorage` today.

(`vinu-news` does have its own FTS at
`vinu_news/analysis/storage/fts.py`, but it's a separate service/schema
and not reusable by `vinu-research`'s hypothesis/reasoning storage.)

**Implication for Step 02:** if hypothesis/reasoning full-text search
turns out to be needed, it is new work — nothing to wire up, only to add.

## Open risks / assumptions

This step exists specifically to eliminate risk elsewhere — it should carry
none of its own beyond "the code may have changed since this plan was
written." If a finding here contradicts something stated elsewhere in this
folder, **the direct source read wins** — go correct the other step file,
don't leave the contradiction standing. (Done for 03, 08, 09 below — see
each file's own updated content.)

## Definition of done

- [x] All five Findings rows filled in with a real answer and a file/line
      citation, not "probably" or "should be."
- [x] Any correction this forces into 03, 08, or 09's assumptions has
      actually been made in those files, not just noted here.
