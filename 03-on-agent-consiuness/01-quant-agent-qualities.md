---
name: quant-agent-qualities
status: definition-phase
purpose: what a trading agent needs — independent of this codebase — to actually function as a quant trader/PM rather than a chatbot with API access. Written after the 1-month replay (the-1-month-back-testing) surfaced concrete evidence of what's missing, not as abstract theory.
---

# What It Takes to Be a Real Quant Trader, Not a Chatbot With Tools

This is deliberately written without reference to `vinu-components`. The
point is to first state what's actually needed, in principle, before
checking what exists — otherwise the answer just becomes "whatever the
codebase already does," which is how the gap stays invisible. The
companion file, `02-vinu-components-where-how.md`, maps this onto the real
codebase.

Three layers, and they have a strict dependency order: **data** grounds
**consciousness**, and **consciousness** governs what **skills** are
allowed to do. A skilled agent with no consciousness layer is just a more
articulate version of the failure this project already found — it doesn't
lack ability, it lacks discipline. Building more skills on top of a broken
consciousness layer makes the failure mode more convincing, not less
dangerous.

---

## 1. Data — what it's allowed to reason from

The rule underneath everything here: **a number the agent states must be
traceable to a real, timestamped source from this session, or it must not
be stated as fact.** Memory of having said something before is not a
source.

- **Its own true state, always fetched live, never recalled.** Cash,
  positions, entry price, real-time P&L, exposure. This is the one
  category that must never tolerate staleness — everything downstream
  (sizing, risk checks, the decision itself) is wrong if this is wrong.
- **Price / volume / quote data, timestamped and freshness-tagged.** The
  agent should always know *how old* a number is, not just what it is. A
  price from this morning and a price from three weeks ago should never be
  presented with the same confidence.
- **Fundamentals and news, source-tagged and timestamped**, with an
  explicit signal for "just happened" vs. "this is what I knew a while
  ago."
- **A structured log of its own past decisions and their outcomes** — not
  raw conversation history, but a queryable record: what it decided, why,
  what it predicted would happen, and what actually happened. Without
  this, the agent cannot learn from being wrong; it can only pattern-match
  on the tone of its last few paragraphs, which is not the same thing as
  updating a belief.
- **Regime / macro context** — volatility regime, correlation structure,
  what kind of market this currently is. The same technical signal means
  different things in different regimes; an agent with no regime context
  is applying one playbook everywhere.
- **Provenance and timestamp metadata on every piece of data**, not just
  the values. "This number came from `get_stock_price` at 09:31 today" is
  a categorically different kind of fact than "I believe this is still
  true."

## 2. Consciousness / harness — the discipline that governs when and how it acts

This is the layer that's usually invisible until it's missing, and it's
the layer that matters most. A trader with perfect market-reading skill
and no discipline still blows up an account; a trader with mediocre skill
and real discipline survives to get better. Concretely:

- **A forced daily ritual, not a suggested one.** Check real state, check
  fresh prices for anything held, re-derive the thesis — every session,
  unconditionally, *before* anything else happens, including looking at
  new ideas. Not something the agent chooses to do when it feels like it —
  something it structurally cannot skip.
- **Structured working memory, not narrative memory.** Position state
  (entry, thesis, invalidation level, size, days held, current P&L) should
  be data the agent reads fresh each time, not prose it has to "remember"
  and inevitably starts paraphrasing — which degrades one repetition at a
  time until the paraphrase no longer resembles the original fact.
- **A hard line between fact and belief.** A number just fetched from a
  real source this turn is a fact. A number recalled from an earlier turn
  is, at best, a belief about what used to be true. An agent that can't
  tell these apart internally will eventually present a belief with the
  same confidence as a fact — indistinguishable to anyone reading its
  output.
- **A risk governor that sits above the reasoning loop, not inside it.**
  Position limits, stop discipline, exposure caps, circuit breakers —
  these cannot be things the agent decides to respect in a good mood.
  They have to be enforced structurally, the same way a real risk desk can
  override a trader regardless of how convinced that trader currently is.
  A governor inside the reasoning loop is just another opinion the model
  can talk itself past.
- **Calibrated self-doubt.** The agent should be able to say "I don't have
  enough here for a real view" and mean it, rather than fabricate a
  plausible-sounding number under pressure to produce *an* answer. A
  confidently wrong answer is worse than a visibly uncertain one, because
  it's indistinguishable from correct to anyone who isn't checking the raw
  data themselves.
- **A real escalation path.** Recognizing when a situation is outside its
  authority or its confidence, and stopping to ask a human — not barreling
  forward because the loop structure expects a decision every turn.
- **Session hygiene that doesn't erode the ritual.** If a session runs for
  weeks, whatever mechanism keeps context bounded (summarization,
  compaction, a fresh session per period) must not be allowed to quietly
  water down the daily ritual itself — compacting old prose is fine;
  compacting away the requirement to re-check today's real state is not.

## 3. Skills — what it can actually do, once 1 and 2 are real

Skills are the least important layer to get right first, and the most
tempting to build first, because they're the most visible and the most
fun to add. In order of what actually matters:

- **Forming a falsifiable thesis**, not a vibe. "Bullish" is not a thesis.
  "Bullish because X, and specifically Y happening would prove this wrong"
  is a thesis — because it gives the discipline layer something concrete
  to check against later.
- **Position sizing that accounts for the whole book**, not one trade in
  isolation — correlation to existing positions, total capital already
  deployed, concentration risk.
- **Execution judgment** — market vs. limit, when a resting stop is
  required rather than optional, what realistic slippage looks like versus
  a frictionless paper fill.
- **Debriefing itself when a position closes** — explicitly comparing what
  it predicted to what happened, and writing that comparison into the
  structured decision log from layer 1. This is the step that actually
  closes the loop between "having a thesis" and "learning from being
  wrong" — without it, the journal is just a record, not a feedback
  mechanism.
- **Reading across signal types**, not defaulting to whichever one tool
  happens to be easiest to call — price/technicals, fundamentals, news,
  cross-asset context — and knowing which of those a specific proven
  mechanism can actually support (e.g., a signal proven to predict
  *magnitude* should never be used to call *direction*, regardless of how
  natural that misuse feels in the moment).

---

## The one-line version

A skilled agent without discipline is a liability with good vocabulary. A
disciplined agent with mediocre skill is at least honest about what it
knows. Build the discipline layer first, verify it holds under real
pressure (not just a clean demo), and only then invest further in skill.
