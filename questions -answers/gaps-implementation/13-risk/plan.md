# Plan - 13 Risk Allocation + Retention

Goal: Safe sizing now, BL/HRP later on 4 guards, prune 90d.

Files touched:
- `vinu-components/vinu-agent/vinu_agent/agent/position_sizing.py:15,20` Kelly + fallbacks + vol targeting + CVaR gate.
- `vinu-components/vinu-agent/teams/risk_gatekeeper/agents/exposure_reviewer/prompt.md:36` concentration + CVaR.
- `vinu-components/vinu-portfolio/service.py:210` parity/HRP switch + 4-guard counts.
- `vinu-components/vinu-agent/vinu_agent/config.py:108,110` budget + advanced knobs.
- Retention: `strategy_store.py`, `results.py:42`, `ticker_ledger.py`, `scheduled/executor.py` DISABLED after 90d dry-run.

Steps:
1. Tail CVaR 95% 3% + vol target 15% 21d. Do first.
2. Auto 4-guard tickers4 strategies18 trades30 live60d. Set once.
3. BL+HRP when guards green. Execution guards pin.
4. Retention prune bulk keep summary, dry-run true 2 weeks.

Knobs: sizing, CVaR, vol, BL/HRP auto, retention 90d/365d (see 10 #24-27,31).
Acceptance: overbet blocked, advanced off until guards green, old rejected DISABLED keep summary.
