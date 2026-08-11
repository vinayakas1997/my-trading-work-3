---
name: angle_synthesizer
role: angle-synthesizer
prompt_file: prompt.md
depends_on: []
tools: [get_all_angles, compare_angles, find_trade_plan_artifact, get_trade_plan_calibration]
skills: []
---

Given one ticker, fetches all 28 vinu-initial-analysis angles for it in
a single tool call and synthesizes an initial read across whichever
angles actually have data. Phase 8 (New-talk-agents/new-thinking/
new-restructure/phases/phase-8-summary-agent-polish/) adds two upstream
checks that strengthen every downstream consumer without them re-deriving
either: compare_angles (deterministic agree/diverge/insufficient_data
between two angles' real values) and get_trade_plan_calibration (a real
trade-plan artifact's historical forecast accuracy, if this ticker has
one -- not a per-angle trust signal, no per-angle calibration tracker
exists anywhere in this system).
