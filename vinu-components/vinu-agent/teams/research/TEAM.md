---
name: research
manager_prompt_file: manager_prompt.md
tools: []
skills: [factor-research]
---

Research team: replaces the standalone `vinu-research` service's loop
("generate idea -> backtest -> risk critic -> iterate until PASS/STOP").
The manager owns that loop; `idea_generator`, `backtest_runner`, and
`risk_critic` are its specialists. `backtest_runner` calls `vinu-simulator`
directly via the existing `run_backtest` tool, unchanged from today.
