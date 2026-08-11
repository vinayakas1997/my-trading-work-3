---
name: theory_reviewer
role: theory-reviewer
prompt_file: prompt.md
depends_on: []
tools: [get_all_angles, get_ticker_summary, query_hypotheses, list_available_features, get_features, get_stock_price, load_skill]
skills: [thesis-intake-strategy-definitions, thesis-intake-risk-rules]
---

Reviews a human-submitted theory against real evidence -- angle data,
the Summary Agent's stored read, and prior hypothesis/evidence history --
plus the two thesis-intake reference skills (what strategy shapes exist,
what disqualifies a theory outright). Structurally cannot write or
execute code: no run_backtest, run_parameter_sweep, or any
code-execution tool is in this list (02-guard-rail.md -- "writes no code,
ever" is enforced by omission, not a prompt instruction).
