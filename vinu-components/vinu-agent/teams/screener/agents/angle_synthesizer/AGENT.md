---
name: angle_synthesizer
role: angle-synthesizer
prompt_file: prompt.md
depends_on: []
tools: [get_cluster_angles, explain_angle]
skills: []
---

Given one ticker AND one of the 7 real clusters (A-G), fetches only that
cluster's own real angles via `get_cluster_angles` and synthesizes a
read for just that cluster. The manager delegates to this specialist
once per cluster per ticker (7 real, independent invocations) rather
than once per ticker handling all 28 angles -- real live-LLM testing
(missing-pieces-of-system/angle-comprehension-hierarchy/
03-real-llm-findings-and-guardrails.md) confirmed the all-28-at-once
design produces a real, confirmed hallucination (an angle cited under
the wrong cluster) and a miscounted angle-coverage total, and that
scoping each call to one cluster's own data -- not just instructing it
to focus on one cluster -- eliminates the cross-cluster mistake
structurally (the data for other clusters is never in this specialist's
context at all) and fixed the coverage-count problem outright (7 of 7
clusters exactly correct vs. 0 of 2 full-book runs correct), at no
measured latency cost.

Cross-angle consensus checks (compare_angles), trade-plan calibration,
and cross-cluster corroboration analysis are NOT this specialist's job
any more -- those are inherently cross-cluster/ticker-level concerns,
moved to the new `cross_cluster_analyst` specialist that runs once per
ticker after all 7 cluster syntheses are back.
