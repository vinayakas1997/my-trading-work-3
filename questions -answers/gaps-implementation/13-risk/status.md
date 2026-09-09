# Status - 13-risk

Date: 2026-09-09
State: doing (tail+vol done, BL/HRP later)
Owner: agent build
Doing: tail CVaR + vol targeting done. Next auto 4-guard + BL/HRP later.
Done:
- position_sizing.py: cvar_exceeds + vol_target_scale 0.25-1x + compute opts cvar_95/current_vol, fail-closed gate, _apply_vol all methods.
Bugs found while implementing: none, defaults disabled until hook wires.
Other files touched:
- vinu-components/vinu-agent/vinu_agent/agent/position_sizing.py
Next: auto 4-guard counts, BL/HRP after ACTIVE 3 + paper 10d, execution guards pin.
