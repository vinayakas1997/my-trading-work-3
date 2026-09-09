# Status - 13-risk

Date: 2026-09-09
State: done (guards; BL/HRP deferred with entry)
Owner: agent build
Doing: tail CVaR + vol targeting done. Next auto 4-guard + BL/HRP later.
Done:
- position_sizing.py: cvar_exceeds + vol_target_scale 0.25-1x + compute opts cvar_95/current_vol, fail-closed gate, _apply_vol all methods.
Bugs found while implementing: none, defaults disabled until hook wires.
Other files touched:
- vinu-components/vinu-agent/vinu_agent/agent/position_sizing.py
Next: none, guards closed. BL/HRP entries below.
Done2:
- service.py: composition action cap VINU_PORTFOLIO_MAX_ACTION 0.20 per cycle + renormalize, 116 green.
BL/HRP deferred (entry: ACTIVE 3 + paper 10d + 60d live; have 0 ACTIVE, 0d live). Guards closed: CVaR gate, vol targeting, DD ladder, action cap.
