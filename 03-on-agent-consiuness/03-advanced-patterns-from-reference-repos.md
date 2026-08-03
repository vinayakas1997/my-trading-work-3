---
name: advanced-patterns-from-reference-repos
status: audit
purpose: what's actually worth stealing from personal-important/other-reference-repos for the consciousness-layer gaps identified in 02-vinu-components-where-how.md. Every claim below is from direct code reading of those repos, not their READMEs or marketing.
---

# What's Actually There, and What's Worth Stealing

Six repos in `personal-important/other-reference-repos/`. The honest split:
**one of them (`Vibe-Trading`) already solved most of the exact problems
`02-vinu-components-where-how.md` identified as missing** — not
approximately, specifically. The rest range from "interesting but doesn't
apply" to "irrelevant."

**This file only has value paired with 02.** 02 is the audit of what's
real in `vinu-components` today (and stays the source of truth for that —
update 02, not this file, once anything below is actually implemented);
this file is where a working answer for each of 02's gaps was found. 02's
gap rows now carry "→ see 03" pointers into the specific points below.

| Repo | Verdict |
|---|---|
| **Vibe-Trading** | ✅ Directly solves 4 of 5 identified gaps. The real payoff. |
| **ref-fincept-terminal** | ⚠️ Confirms the failure pattern is common (built risk/confirmation gates, never wired in) + one reusable audit-log schema. |
| **ref-FinRobot** | ⚠️ Interesting multi-agent orchestration pattern, but doesn't address any of our 5 gaps — no journal, no fact-freshness, no critic role, no confidence output. |
| **ref-FinRL-Meta** / **ref-FinRL-Trading** | ❌ Pure RL/quant repos, zero LLM-agent code. Not relevant to this layer at all (they matter for the feature-engine/simulator work `new_repos_and_some_understanding.md` already scoped separately). |

---

## Vibe-Trading — the real find

Not a single chatbot loop. It's a core ReAct loop (`agent/src/agent/loop.py`)
plus a genuine multi-agent swarm layer (`agent/src/swarm/`), a scheduler,
and a separate live-trading runtime — architecturally more mature than
`vinu-agent` in exactly the places `vinu-agent` is thin.

**Maps directly onto the 5 gaps from `02-vinu-components-where-how.md`:**

1. **Forced fresh-data verification** — `agent/src/swarm/grounding.py`.
   Before a worker starts reasoning, it scans for tickers, force-fetches
   real OHLCV, and injects a "Ground Truth" block with an explicit
   instruction: *"Do NOT cite prices from your training data — when you
   state a price, cite the date from this table."* This is **structural
   pre-injection**, not a self-check the model has to remember to do —
   exactly the shape of fix `02-vinu-components-where-how.md` recommends
   (a forced gate, not a prompt suggestion). Not a hard block on
   zero-tool-call turns the way I was mid-designing before — it solves the
   problem differently, by pre-loading fresh ground truth before reasoning
   even starts, which is arguably cleaner than forcing a tool call after
   the fact.

2. **Structured decision journal, distinct from chat history** — two real
   mechanisms:
   - `agent/src/skills/thesis-tracker/SKILL.md`: a per-holding thesis file
     (`reports/{company}-thesis.md`) with a 5-sentence core thesis, a
     **falsifiable assumptions table**, explicit red-lines, and a
     quarterly re-check that produces a 1–10 health score plus a
     hold/add/trim/exit verdict. This is almost exactly the "falsifiable
     thesis with invalidation criteria" quality from `01-quant-agent-
     qualities.md` — and it's a *file-based, symbol-keyed* record, not
     something buried in conversation history.
   - `agent/src/hypotheses/registry.py` (`HypothesisRegistry`): JSON-backed
     registry with a real status lifecycle (`exploring → testing →
     validated → rejected → monitoring`) and an `invalidation_notes` field.
     This is the "structured decision/outcome journal" `02-vinu-components-
     where-how.md` flagged as entirely missing from `vinu-components` —
     confirmed missing there, confirmed present and working here.

3. **Fact-vs-belief / anti-fabrication** — the strongest single finding.
   `agent/src/tools/report_audit_tool.py` is a **two-phase extract → verdict
   audit**: after a report is written, it samples the numeric claims in it
   and cross-checks each one against a freshly-fetched authoritative value
   (1% tolerance). This is a genuine, structural post-hoc "did you just
   make that number up" gate — precisely the mechanism that would have
   caught the fabricated JNJ price in the 1-month replay before it ever
   reached the agent's final answer, let alone got repeated 13 times.
   `agent/src/tools/financial_rigor_tool.py` (`cross_validate`, exact-Decimal
   arithmetic) is the same idea applied to arithmetic drift.

4. **Risk governor above the reasoning loop** — `agent/src/live/
   enforcement.py` (`check_mandate`), a fail-closed, non-LLM policy gate
   enforced at order time. This is **the same pattern** `vinu-components`
   already has and does well (`TradingMandate`/`OrderGuard`) — good
   independent confirmation that this design choice is the right one, not
   new information to act on.

5. **Escalation/low-confidence** — the one gap this repo only partially
   solves. The swarm chair persona is *instructed* to say "under missing
   X, conclusion confidence is Y" (`swarm/presets/value_investing_committee
   .yaml`) — soft, prompt-level, not a hard mechanism. No refusal tool that
   halts execution below a confidence threshold. Worth noting honestly:
   nobody in these six repos solved this one structurally. It stays a real
   open problem.

**Also notable, not mapped to the 5 gaps but worth knowing about:**
- Session compaction preserves a "Resolved Questions / Key Decisions"
  section across compression (`loop.py`, `_STRUCTURED_SUMMARY_PROMPT`) —
  more deliberate than `vinu-agent`'s compaction, which just shrinks/drops
  old tool output with no concept of "decisions worth keeping."
- `agent/src/memory/persistent.py` freezes memory as a snapshot at session
  start rather than updating it live mid-session — a deliberate trade-off
  for prompt-cache efficiency, worth understanding before copying blindly.

---

## ref-fincept-terminal — a cautionary confirmation, plus one reusable schema

Real LLM-agent chat/orchestration exists here (`AgentService_Execution.cpp`,
MCP tool-calling layer) — not just a dashboard. Two findings matter:

- **The exact same "governor built, never wired in" failure exists here
  too.** `RiskManager::validate_order()`/`is_order_allowed()` is a complete,
  well-designed risk gate — and grepping the entire repo for callers
  outside its own class returns **zero results**. Same for
  `ConfirmationService` (staged human approval for live orders) — defined,
  never called from the live-order tool path. This is useful less as
  something to copy and more as confirmation that "built a safety
  mechanism, forgot to actually gate the dangerous path with it" is a
  common, repeatable mistake — worth treating as a specific checklist item
  ("is this governor actually in the call path, verified by grep, not just
  present in the codebase") whenever anything similar gets built for
  `vinu-agent`.
- **`AuditLogger`'s schema is worth reusing as-is**: `AuditEntry{id, action,
  workflow_id, node_id, symbol, details, metadata(JSON), paper_trading,
  timestamp}`, with an action enum covering `RiskCheckPassed/Failed`,
  `ConfirmationApproved/Rejected`, `OrderPlaced/Filled`. It's event
  logging, not a predicted-vs-actual journal (doesn't close the "did I
  learn from being wrong" loop the way Vibe-Trading's `HypothesisRegistry`
  does) — but as a base audit-trail shape it's clean and directly
  portable.

## ref-FinRobot — architecturally interesting, doesn't solve our problem

Built on AutoGen (`ConversableAgent`/`GroupChat`). Has a real leader/worker
delegation pattern (`MultiAssistantWithLeader`, `finrobot/agents/workflow
.py:397-469`) — a manager agent issues `[<staff>] <order>` commands to
worker agents sequentially. That's a legitimate multi-agent pattern, but
it's sequential task-handoff, not a debate or a second-opinion/critic
check. Confirmed via direct grep: **no journal, no fact-freshness
mechanism, no critic/verifier role, no structured confidence output, no
escalation mechanism anywhere in the repo.** The actual trading demos
(`agent_fingpt_forecaster.ipynb`, `agent_trade_strategist.ipynb`) use a
single assistant + a plain executor — the same single-loop shape
`vinu-agent` already has. Nothing here is a priority pull; the leader/
worker pattern is only worth remembering if a future adversarial-review
step gets designed (see recommendation below).

## ref-FinRL-Meta / ref-FinRL-Trading — not relevant to this layer

Pure RL/quant repos. Every "agent" reference is a DRL model wrapper
(stablebaselines3/elegantrl), not an LLM agent. Zero orchestration, memory,
journaling, or risk-consumption code relevant to the consciousness layer.
These matter for the separate feature-engine/simulator work already scoped
in `new_repos_and_some_understanding.md` (qlib's factor engine, FinRL-
Meta's slippage modeling) — different layer, not this one.

---

## Recommendation — what to actually pick, in priority order

1. **`report_audit_tool`'s extract → verdict pattern** (Vibe-Trading) —
   highest leverage, directly prevents a repeat of the fabricated-JNJ-price
   failure. Cheapest to justify: it's a post-hoc check, doesn't require
   redesigning the core loop.
2. **`grounding.py`'s forced pre-reasoning data injection** (Vibe-Trading)
   — the cleanest fix for "agent stops calling tools and goes quiet."
   Rather than trying to detect and force a retry after the fact (what I
   was mid-designing before this detour), inject fresh ground-truth data
   *before* the model starts reasoning each turn, for every held position
   at minimum. Structurally can't be skipped because it's not the model's
   choice to make.
3. **A `HypothesisRegistry`/thesis-tracker equivalent** (Vibe-Trading) —
   this is the structured decision journal `02-vinu-components-where-how
   .md` flagged as entirely missing. Gives `generate_trade_plan`'s
   already-real invalidation rules somewhere persistent to live, and
   closes the predicted-vs-actual loop `01-quant-agent-qualities.md` calls
   the actual learning mechanism.
4. **`AuditLogger`'s event schema** (fincept-terminal) — cheap, mechanical,
   worth adding alongside #3 as the lower-level "what happened, when" log
   underneath the higher-level thesis/hypothesis journal.
5. **Explicitly punt on hard escalation/confidence-thresholding** — nobody
   in these six repos solved it structurally, and it's genuinely a harder
   design problem (what does an LLM saying "I'm not confident" actually
   block, and how does that not become a way to avoid ever making a call).
   Worth its own dedicated design pass later, not bundled into this batch.

Not recommending the FinRobot leader/worker pattern or a full adversarial
multi-agent swarm right now — `01-quant-agent-qualities.md`'s own ordering
says consciousness before more architecture, and items 1-4 above are
smaller, targeted, and directly evidenced by the actual replay failure,
versus a multi-agent redesign that would be architecture-first without a
concrete problem it's solving yet.
