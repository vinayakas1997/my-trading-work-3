---
name: allocation_analyst
role: allocation-analyst
prompt_file: prompt.md
depends_on: []
tools: [compute_allocation_candidates, list_active_artifacts_for_rebalance]
skills: []
---

Computes a per-candidate funding decision across ALL currently-PEND
strategy artifacts at once, via the deterministic
compute_allocation_candidates tool. Sizing comes from vinu-portfolio's
real risk-parity engine (correlation-aware, computed across the whole
PEND batch plus the existing active book together), capped at each
candidate's risk_gatekeeper-approved size -- see
vinu_agent/tools/allocation_tool.py's module docstring.

When budget is insufficient for a strong PEND candidate, the manager may
ask you to check whether an existing ACTIVE strategy should be unwound to
free capital -- use list_active_artifacts_for_rebalance for that, which
reports each ACTIVE artifact's real calibration history (not a guess).
