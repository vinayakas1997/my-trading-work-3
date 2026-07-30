---
name: 01-verification-pass
status: Not Started
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

*(Fill in as each substep completes. Leave "TBD" for anything not yet
checked — do not guess, and do not let a downstream step treat a TBD as an
answer.)*

- Risk critic (`llm.py::_build_risk_critic_prompt`): TBD
- Loop stop condition (`loop.py`): TBD
- News angle exposure (`vinu-news`): TBD
- Live kill switch (`vinu-live`, `routes_broker.py`): TBD
- FTS5 existing in `sqlite_backend.py`: TBD

## Open risks / assumptions

This step exists specifically to eliminate risk elsewhere — it should carry
none of its own beyond "the code may have changed since this plan was
written." If a finding here contradicts something stated elsewhere in this
folder, **the direct source read wins** — go correct the other step file,
don't leave the contradiction standing.

## Definition of done

- [ ] All five Findings rows filled in with a real answer and a file/line
      citation, not "probably" or "should be."
- [ ] Any correction this forces into 03, 08, or 09's assumptions has
      actually been made in those files, not just noted here.
