# Vectorbt Not Connected Yet - Inefficiency (2026-09-08)

Simple English.

## What is vectorbt?
Vectorbt is a fast test tool. It tests many parameter sets together.
Example: `fast 5 slow 30`, `fast 10 slow 40`, `fast 20 slow 60` in one go.
It uses vector parallel, not one by one loop.

## What means not poly wired / not connected?
Not connected means sweep engine does not use vectorbt yet.
Today `backtest_runner` uses slow loop:
- 1 candidate -> 1 simulate -> 1 Sharpe
- 190s for 1, 55s for 1, 219s for 1
- 5 candidates = about 15 min

If wired:
- 5 to 10 candidates together -> rank together
- About 10s, not 190s

File refs: `inefficiencies-A-J.md:E`, `03/vectorbt-sweep.md`,
`run_parameter_sweep_tool.py`, `loop.py:141 N=5`.

## Why wire it basically?
To make idea to test to rank fast.
- Full needs 5 tries, PBO, walk-forward, deflated 0.95.
- Slow loop cannot try many. It always stops at 1 crossover.
- Fast sweep lets agent try crossover, then RSI, then Bollinger, then MACD+RSI mix.
- Then risk can check quickly.

So wired = fast = effective. Not wired = slow = always crossover gap.

## Today status
Open. Not wired. Slow loop only.
AAPL 102 trades 190s STOP. MSFT STOP. NVDA fail then 200 after fix.
No `completeness 0.7`, no `PBO`, no `rank_candidates` table yet.

## Next to wire (one by one)
1. Mature prompt first (diverse recipe).
2. Wire vectorbt sweep for `run_parameter_sweep`.
3. Then 5 iters + holdout + PBO + stress.
4. Then risk PEND -> capital ACTIVE -> shadow -> monitor.

Keep this file for tracking. When wired, update status to Done with time.
