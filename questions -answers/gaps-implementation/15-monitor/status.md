# Status - 15-monitor

Date: 2026-09-09
State: doing (HALT+time-stop done, rest open)
Owner: agent build
Doing: HALT entries-only + time-stop done. Next trailing + vol + cooldown.
Done:
- orchestrator.py: HALT_POLICY entries_only allow exits/reduces, all = old block. Time-stop age>MAX_HOLD_DAYS 30 auto exit.
- tests: old block test pinned to all, new test entries_only allows exit.
Bugs found while implementing: none, auth 2 failures pre-existing not ours.
Other files touched:
- vinu-components/vinu-live/vinu_live/trade_plan/orchestrator.py
- vinu-components/vinu-live/tests/test_trade_plan_orchestrator.py
Next: trailing 2x ATR default, vol scaling, cooldown 2 losses lock 24h.
