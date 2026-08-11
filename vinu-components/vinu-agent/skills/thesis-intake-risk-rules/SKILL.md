---
name: thesis-intake-risk-rules
description: What disqualifies a human-submitted theory outright, before it's even worth checking against real data -- read by the thesis_intake team's theory_reviewer. Every edit to this file is logged by agent/skill_audit.py (Phase 6's skill-edit audit log).
category: strategy
---

## What disqualifies a theory outright

These are hard stops -- if any applies, the verdict is "doesn't hold up"
regardless of how much real supporting evidence exists elsewhere. Cite
the specific rule in the verdict, not a vague "too risky."

1. **No real, checkable claim.** "AAPL will go up" with no mechanism,
   timeframe, or condition attached is not a theory, it's a guess. A
   theory must state what would make it TRUE and what would make it
   FALSE against real data -- if the reviewer can't articulate what
   evidence would contradict it, it fails here, before any data is even
   pulled.
2. **Contradicted by already-recorded evidence for this exact ticker.**
   If `HypothesisRegistry`/`TickerLedger` already shows a directly
   contradicting, real, cited result for this symbol (not just "similar"
   -- see the near-duplicate check in `agent/thesis_intake_gate.py`,
   which is a separate, earlier check from this one), the theory doesn't
   get to relitigate settled evidence without addressing why this time is
   different.
3. **Depends on data the pipeline cannot actually access.** A theory that
   requires, say, options flow, insider-trading data, or anything outside
   the real angle/indicator/price data this system actually has is not
   checkable here -- say so plainly, don't approximate with a proxy the
   human didn't ask for.
4. **Implies leverage, position sizing, or timing outside the real
   mandate.** A theory that only "works" using leverage or concentration
   beyond `TradingMandate`'s real configured limits (see
   `vinu_agent/broker/mandate.py`) is disqualified as stated -- the
   mandate isn't something Thesis Intake can waive.
5. **No symbol, or a symbol not in the watchlist/universe this pipeline
   actually tracks.** A theory about a name this system has no data
   pipeline for at all cannot be checked, full stop.

**None of these are about whether the theory is likely to be profitable**
-- that's what the downstream research loop's own statistical bar
(deflated Sharpe, holdout, stress test, PBO) is for. This list is only
about whether the theory is even a real, checkable claim this pipeline
can act on.
