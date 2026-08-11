---
name: thesis_intake
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---

Thesis Intake team: a second entry point alongside the watchlist (Phase
6, New-talk-agents/new-thinking/new-restructure/phases/
phase-6-thesis-intake/). A human hands the pipeline a raw theory -- an
idea or analogy, not code, not even a formal recipe -- and it gets
checked against real evidence before it's allowed to consume any of the
pipeline's downstream budget. Only reached after THGATE (agent/
thesis_intake_gate.py) passes -- a cheap, deterministic, no-LLM
near-duplicate + shared-cap check that runs before this team is ever
delegated to, not inside it. Writes no code, ever -- the tool list below
structurally excludes run_backtest/run_parameter_sweep/any code-execution
tool, not a prompt instruction. On a "worth checking" verdict, hands off
to the research team's manager loop (Phase 1) -- same downstream loop any
system-generated idea uses, different front door.
