---
name: backtest_runner
role: backtest-runner
prompt_file: prompt.md
depends_on: [idea_generator]
tools: [run_backtest]
skills: []
---

Runs the candidate strategy through `vinu-simulator`'s
`/simulator/simulate/custom` endpoint via the existing `run_backtest` tool
(unchanged) and reports back the metrics clearly.
