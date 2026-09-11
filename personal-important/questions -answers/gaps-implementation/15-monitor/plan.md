# Plan - 15 Monitor Shock Exit

Goal: Safe live monitor, entries-only HALT, time-stop first.

Files touched:
- `vinu-components/vinu-live/trade_plan/orchestrator.py:107,223,389,398,428,430,486,511,658` cycle/shock/invalidation/rebalance/HALT/trailing/reconcile.
- `vinu-components/vinu-live/breaker/engine.py:25`, `limits.py:9` daily 5%.
- `vinu-components/vinu-live/live_metrics.py:28` live metrics.

Steps:
1. HALT entries-only allow exits + time-stop 30d. Highest safety.
2. Trailing 2x ATR default + vol scaling + cooldown 2 losses lock 24h.
3. Bracket partial 50% at 1R + turbulence VIX pause entries.
4. Tests: crash exit allowed, expiry exit, trailing up never down, lock works.

Knobs: HALT_POLICY, MAX_HOLD_DAYS, TRAILING, VOL_SCALING, COOLDOWN, BRACKET, TURBULENCE (see 10).
Acceptance: stuck falling fixed, loser expiry exits, revenge blocked.
