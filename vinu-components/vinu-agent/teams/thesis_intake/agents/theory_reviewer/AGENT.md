---
name: theory_reviewer
role: theory-reviewer
prompt_file: prompt.md
depends_on: []
tools: [get_all_angles, get_ticker_summary, query_hypotheses, get_signal_evidence, list_available_features, get_features, get_stock_price, load_skill]
skills: [thesis-intake-strategy-definitions, thesis-intake-risk-rules]
---

Reviews a human-submitted theory against real evidence -- angle data,
the Summary Agent's stored read, prior hypothesis/evidence history, and
recorded must-condition trigger history (get_signal_evidence -- e.g. a
submitted theory built around an SMA(5)/SMA(50) cross can be checked
against real recorded trigger counts and outcomes for that ticker, not
just theory) -- plus the two thesis-intake reference skills (what
strategy shapes exist, what disqualifies a theory outright). Structurally
cannot write or execute code: no run_backtest, run_parameter_sweep, or
any code-execution tool is in this list (02-guard-rail.md -- "writes no
code, ever" is enforced by omission, not a prompt instruction).
