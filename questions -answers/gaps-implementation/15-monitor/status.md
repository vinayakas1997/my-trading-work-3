# Status - 15-monitor

Date: 2026-09-09
State: doing (HALT+time-stop+cooldown done, rest open)
Owner: agent build
Doing: HALT + time-stop + cooldown done. Next trailing + bracket + turbulence.
Done:
- orchestrator.py: HALT_POLICY entries_only allow exits, time-stop 30d auto exit.
- orchestrator.py: cooldown_active 2 losses lock 24h entries only, exits never blocked, 30 green.
Bugs found while implementing: mock db_path fallback fixed with Path exists check.
Other files touched:
- vinu-components/vinu-live/vinu_live/trade_plan/orchestrator.py
- vinu-components/vinu-live/tests/test_trade_plan_orchestrator.py
Next: bracket 50% at 1R (needs partial_taken state, schema change).
Done3:
- orchestrator.py: trailing_stop_for 2x ATR proxy ratchet up longs down shorts never loosen, 30 green.
Done4:
- orchestrator.py: turbulence_active 14d vol > 0.05 pauses entries exits never blocked, calm False wild True, 30 green.
