---
name: risk_gatekeeper
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---

Risk gatekeeper team: final approve/reject gate on a research-produced
strategy artifact (status BENCHING or MONITORING) against the CURRENT
real portfolio -- not whether the strategy is good (research's own
risk_critic already answered that), only whether it fits within real
risk limits right now. APPROVED transitions the artifact to PEND (not
directly ACTIVE) via SqliteStrategyStore.mark_pend(), carrying a real
approved_size -- funding itself is capital_allocator's later, batched
decision (Phase 2, New-talk-agents/new-thinking/new-restructure/phases/
phase-2-funding-mechanics/). REJECTED leaves the artifact untouched.
