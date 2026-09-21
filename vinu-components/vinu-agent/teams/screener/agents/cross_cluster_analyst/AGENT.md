---
name: cross_cluster_analyst
role: cross-cluster-analyst
prompt_file: prompt.md
depends_on: [angle_synthesizer]
tools: [get_all_angles, compare_angles, find_trade_plan_artifact, get_trade_plan_calibration]
skills: []
---

Runs once per ticker, after all 7 `angle_synthesizer` cluster calls are
back. Does the three things that are inherently cross-cluster/ticker-
level, not a single cluster's job:

1. Cross-angle consensus checks (`compare_angles`) -- moved here
   verbatim from `angle_synthesizer`'s old Phase 8 material, since a
   real comparable pair (e.g. `arima`/`chronos`) can span two different
   clusters (A and B), which no longer fits inside one cluster-scoped
   call.
2. Trade-plan calibration read (`find_trade_plan_artifact` +
   `get_trade_plan_calibration`) -- also moved here, ticker-level, not
   per-cluster.
3. **New**: real cross-cluster analysis ("Chapter 3" in
   missing-pieces-of-system/angle-comprehension-hierarchy/) -- given the
   7 real cluster synthesis sentences `angle_synthesizer` already
   produced, finds genuine corroboration between independent clusters
   and flags clusters showing no real cross-timeframe change. Real
   testing (03-real-llm-findings-and-guardrails.md) found this step
   never fabricated a claim (every corroboration traced back to a real
   cluster sentence), but was inconsistent about *which* 2 of 3
   genuinely-relevant clusters it surfaced together across repeated,
   very similar runs -- worth knowing when reading its output, not yet
   fixed.

This specialist gets `get_all_angles` (not the cluster-scoped tool) --
unlike `angle_synthesizer`, its whole job is comparing across clusters,
so seeing everything is correct here, not the mistake the cluster split
was built to prevent.
