---
name: backtest_runner
role: backtest-runner
prompt_file: prompt.md
depends_on: [idea_generator]
tools: [run_backtest, run_parameter_sweep]
skills: []
---

Runs the candidate through `vinu-simulator`. Two paths depending on what
idea_generator handed over (Phase 1, New-talk-agents/new-thinking/
new-restructure/phases/phase-1-sweep-engine-wiring/): raw code -> the
existing `run_backtest` tool (unchanged); a recipe + param grid -> the new
`run_parameter_sweep` tool, which also requires a self-verdict
(completeness + PBO) before handing off -- see prompt.md.
