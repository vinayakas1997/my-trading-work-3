# Deep Dive — AI4Finance-Foundation/FinRL (16.2K) + TradeMaster (3.1K)

> Source: `https://github.com/AI4Finance-Foundation/FinRL` (`examples/FinRL_StockTrading_2026_*.py`), successor `FinRL-Trading` (FinRL-X).

## What to look at

- `examples/FinRL_StockTrading_2026_1_data.py` — DOW30 download + VIX/turbulence.
- `examples/FinRL_StockTrading_2026_2_train.py` — trains 5 agents (A2C, DDPG, PPO, TD3, SAC).
- `examples/FinRL_StockTrading_2026_3_Backtest.py` — backtest vs MVO/DJIA.

## Clone & inspect

```bash
git clone https://github.com/AI4Finance-Foundation/FinRL --depth 1
cat examples/FinRL_StockTrading_2026_2_train.py | head -n 80
```

## Extractable for Vinu

1. **5-agent bake-off** → plug into `vinu-simulator/engine/simulator.py:300` `SimulatorEnv` — compare vs your single-voice self-verdict `04:253` (pending Row 6). Provides adversarial baseline.
2. **Turbulence/VIX feature** → `vinu-tools/` as regime feature for `capital_allocator` vol-adjusted sizing (adoptable Row 23).
3. **FinRL-Meta envs** → Gym-style market envs for parameter sweeps.

## Note

For production, use successor `AI4Finance-Foundation/FinRL-Trading` (FinRL-X) — decoupled modular, not monolith.
