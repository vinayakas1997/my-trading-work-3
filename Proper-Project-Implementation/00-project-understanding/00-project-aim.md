# Project aim

## One sentence
An autonomous system that, around the clock (24 hours, five days a week), finds stocks worth looking at, builds and proves trading strategies for them, decides how much capital each may use, trades them on an Alpaca **paper** account, and learns from the real results.

## The loop (what the system must do, end to end)
1. **Screener** picks the top 10 stocks.
2. **Analysis** describes each one: regime, trend, news, session behaviour.
3. **Strategy writing:** an AI writes a strategy, or a ready-made one is chosen, or the user adds one.
4. **Research:** test on every bar size, under regular hours and all 24 hours; simulate; optimise; the **code** decides PASS (never the AI).
5. **Retry:** a failed strategy is rewritten using the failure reasons (3 attempts).
6. **Fate keeper:** the risk gatekeeper checks it, then the capital allocator gives it a budget and its approved sessions.
7. **Paper trading:** orders go through the order guard to Alpaca (paper).
8. **Live feedback:** real fills and results go back into research.

## Fixed constraints
- Alpaca **paper** only. Equities only.
- Keys only in `vinu-components/secrets/`.
- The `models` container stays dormant (never built or started).
- The AI never touches the broker directly; the order guard and the kill switch sit between them.
- No evidence, no trading: a stock, bar size or session that has not been measured is not traded.
- Real data stays real. Synthetic data is used only inside isolated tests, running the real code, and a no-edge case must be rejected.

## What "done" means
The whole loop runs without a person, every number on the scoreboard (`scripts/pipeline_health.py`) is checked against the real system, and every error ever fixed has a test that fails if it returns (see `03` problem log when it exists).

## Files in this folder
- `vision-trading-system.md`: the consolidated vision (copy of `newer-thinking-with-discussed/vision-trding-system.md`) with **Part D: the 24-hour system** added at the end.
