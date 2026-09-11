# Plan - 07 Sweep 7 Inefficiencies

Goal: Fix 7 sweep gaps one by one, fastest first.

Files touched:
- `vinu-components/vinu-agent/teams/research/agents/idea_generator/prompt.md:40` base_code link (No.4+No.2).
- `vinu-components/vinu-agent/vinu_agent/tools/run_parameter_sweep_tool.py:40` base_code mode.
- `vinu-components/vinu-research/vinu_research/sweep_grid.py:37,39` PBO 2+ rule (No.5).
- `vinu-components/vinu-agent/vinu_agent/agent/planner_triage_hook.py:143,104` angle fit + K-cap (No.6+No.7).
- `vinu-components/vinu-agent/vinu_agent/agent/thesis_intake_gate.py:21` human priority.
- Interval plumbing for 1H sweep (No.1).

Steps:
1. No.4 prompt 5 lines base_code param_name + grid.
2. No.2 LLM coarse grid for custom MACD+rsi.
3. No.5 require 2+ succeeds else FAIL.
4. No.1/No.6/No.7 after 1-3 green.

Knobs: `VINU_SWEEP_INTERVALS`, `TOP_N`, `MIN_SUCCEEDS_FOR_PASS=2` (see 10).
Acceptance: custom strategy gets grid, no lucky PASS, 1H sweep runs after 1D.
