---
name: risk_critic
role: risk-critic
prompt_file: prompt.md
depends_on: [backtest_runner]
tools: []
skills: []
---

Reviews the strategy and its backtest metrics, returns a PASS/STOP
verdict with reasoning. Was `vinu_research/llm.py`'s risk-critic LLM
call — see implementation notes for what was simplified in this port
(the old deterministic rules-based pre-pass isn't carried over yet).
