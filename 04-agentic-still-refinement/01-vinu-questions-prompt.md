---
name: vinu-questions-prompt
status: definition-phase
purpose: the daily ritual/checklist an agent session must actually answer, in order, every day — the operational form of "a forced daily ritual, not a suggested one" from 03-on-agent-consiuness/01-quant-agent-qualities.md. Synthesizes the four items in 03-on-agent-consiuness/01-plan-and-implementations/ into one artifact instead of leaving them as separate mechanisms the agent has to remember to combine. Nothing here is implemented yet.
---

# The Daily Ritual — 8 Questions a Session Must Answer

## Why this file exists

`03-on-agent-consiuness/01-plan-and-implementations/` defined four separate
fixes (fact-verification audit, forced ground-truth injection, structured
decision journal, audit-log schema) for four separate failures the 1-month
replay found. Those are mechanisms. What was still missing was the actual
**shape of a session** — the concrete set of questions a trading session
should be forced to answer, in order, using those mechanisms, before it's
allowed to do anything else. This file is that shape.

**This only works if every answer below is forced to come from real,
structured data (item 2's injected ground truth, item 3's journal), not
free-written by the model from memory.** If these 8 questions get answered
the same way the replay's "Technical Analysis Update" paragraphs were —
fluent, confident, unverified — this becomes a more convincing version of
the exact failure that started this investigation, not a fix for it. The
checklist is the shape; the four items in `01-plan-and-implementations/`
are what make the answers real instead of plausible-sounding.

## The 8 questions, and what actually answers each one

### 1. Which tickers should I focus on today?

Not yet built anywhere. Needs a watchlist/opportunity scan grounded in
regime context — `01-quant-agent-qualities.md` §1's "regime/macro context"
data category. Depends on `vinu-initial-analysis`'s stored angle output
(significance_score, regime_features) being consulted correctly per the
signal-usage-contract gap below (question 6) — a ticker shouldn't get
flagged "focus today" off a signal that isn't proven to support that call.

### 2. What is the risk management?

Already real, already confirmed wired into the live order path:
`TradingMandate`/`OrderGuard` (`vinu_agent/broker/mandate.py`). This
question's answer should be a direct read of the current mandate state
(position limits, exposure caps), not a narrative restatement — the
governor sits above the reasoning loop per `01`'s consciousness layer, this
question just surfaces its current state at session start.

### 3. What is the history/knowledge of this ticker?

Not built yet — this is exactly what
[`03-structured-decision-journal.md`](../03-on-agent-consiuness/01-plan-and-implementations/03-structured-decision-journal.md)
is for: a queryable record of prior theses, invalidation levels, and status
per symbol, instead of the agent trying to recall this from raw
conversation history (which is how the replay's paraphrase-drift happened
in the first place).

### 4. How did it perform in the last live trades?

Also the structured decision journal (item 3) — specifically its
predicted-vs-actual field. This is the "debriefing itself when a position
closes" skill from `01-quant-agent-qualities.md` §3: comparing what was
predicted to what happened. Without item 3 existing, this question has no
real data to answer from and will get a narrative, unverifiable answer —
do not build this question's UI/prompt before item 3 exists underneath it.

### 5. What should the plan be?

Already real, already exists, but dormant: `generate_trade_plan`
(`vinu_agent/tools/trade_plan_tool.py`) already produces a real entry
checklist with invalidation/exit rules from regime analysis, factors,
backtest validation, and news sentiment — confirmed never called during
the entire 1-month replay. This question's job is to force that call, not
to build new plan-generation logic that duplicates it.

### 6. Which strategy should I apply today?

**This is the signal-usage-contract gap** — confirmed missing, not yet
written up as its own item file. `significance_score` is validated for "is
this news event significant" (real, leakage-checked AUC — see
`01-the-stage-2-claude/testing-status/significance-classifier-improvement/
test-log.md`) but **not** for direction (confirmed twice, ~50% coin-flip,
`01-the-stage-2-claude/full-plan.md:68-74`). Answering "which strategy
today" requires knowing which of the available signals can actually
support the kind of call being made — direction vs. magnitude vs.
significance — and nothing today tells the agent that boundary explicitly.
Needs its own design pass (see "What's still missing" below).

### 7. What inconsistencies exist between market prep and (past history + known knowledge)?

This is
[`01-fact-verification-audit.md`](../03-on-agent-consiuness/01-plan-and-implementations/01-fact-verification-audit.md)'s
extract→verdict pattern — but run **forward**, before the day's plan is
committed to, not only after a response is composed. Item 1 as currently
scoped catches a fabricated number after the fact; this question asks for
the same audit logic applied prospectively: does today's fresh data
(item 2's injection) actually contradict what the session believes from
its own journal (item 3) or prior turns? Worth folding into item 1's design
rather than building a second, separate audit mechanism — flag this in
item 1's file when it's picked up for implementation.

### 8. What is the risk, or how should I behave in this situation?

Two different things bundled in one question, deliberately kept together
here because they're both "consciousness layer" per `01`:
- The *quantifiable* part (position risk, exposure) is item 2's forced
  ground-truth injection plus the existing `TradingMandate`.
- The *qualitative* part ("how should I behave" — when to defer, when to
  say "not enough information") runs straight into the one thing this
  entire project has already confirmed is unsolved anywhere, including all
  six reference repos in `personal-important/other-reference-repos/` (see
  `03-on-agent-consiuness/03-advanced-patterns-from-reference-repos.md`
  §"Escalation/low-confidence"). This question doesn't solve that gap — it
  makes it visible and honest every session instead of hidden, which is
  itself worth having even before the gap has a real fix.

## What's still missing, not yet written up as its own item

- **The signal-usage contract** (question 6) — a concrete answer to "what
  is `significance_score`/regime_features/sentiment each actually proven
  to support, and what happens if the agent tries to use one for something
  it doesn't support (e.g. direction)." Candidate home: either its own 5th
  item file in `03-on-agent-consiuness/01-plan-and-implementations/`, or
  folded into item 2 (forced ground-truth injection) as an extra injected
  block — not yet decided, flagged here so it doesn't get lost.
- **Prospective fact-checking** (question 7) — extending item 1's
  extract→verdict audit to run before a plan is committed to, not only
  after a response is composed.
- **Hard escalation/self-doubt** (question 8's qualitative half) —
  explicitly out of scope for the current plan, confirmed unsolved
  everywhere researched so far. Not attempting a fix here; naming it
  honestly every session is the only thing currently proposed.

## Related documents

- [`03-on-agent-consiuness/00-start-here.md`](../03-on-agent-consiuness/00-start-here.md)
  — full context chain for why this ritual is needed at all (the replay
  failure this whole line of work responds to).
- [`03-on-agent-consiuness/01-quant-agent-qualities.md`](../03-on-agent-consiuness/01-quant-agent-qualities.md)
  — "a forced daily ritual, not a suggested one" is this file's direct
  source.
- [`03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md`](../03-on-agent-consiuness/01-plan-and-implementations/AGENTS.md)
  — the four mechanisms this ritual's questions are built on top of.
