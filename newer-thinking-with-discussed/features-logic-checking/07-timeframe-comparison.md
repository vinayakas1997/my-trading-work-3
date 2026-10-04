# Which bar size suits the pullback strategy? (backtest, 2022-01-03 to 2026-10-02)

Setup tested = `trend_pullback_long` must-conditions: close above its 50-bar average, below its 5-bar average, ADX(14) above 20. Held 20 bars after each setup, long only. Run through the real simulator (`scripts/compare_timeframes.py`) on AAPL, MSFT, GOOGL, AMZN, META, using the same rules on every bar size. Mean over the 5 stocks:

| Bar size | Sharpe | Total return | Max drawdown | Trades per stock |
|---|---|---|---|---|
| 15 minutes | −2.95 | −45% | −47% | 89 |
| 1 hour | −0.22 | −17% | −44% | 98 |
| 4 hours | +0.25 | +27% | −38% | 59 |
| 1 day | +0.34 | +42% | −30% | 21 |
| *Buy and hold, same stocks and period* | *+0.57* | *+90%* | *−48%* | |

## What this says

* The shorter the bar, the worse the result. 15-minute is clearly losing (every stock negative); 1-hour is roughly flat to negative.
* **No bar size beats simply holding the stocks.** Daily has the best risk numbers of the four (smaller drawdown than holding) but a lower Sharpe and about half the return.
* Daily and 4-hour are the only ones with a positive Sharpe, and they come from few trades (about 21 and 59 per stock). Four bar sizes were compared, so the best-looking one is partly luck.

## What this does not say

* The live strategy also has a 5% (daily) stop, scaled for shorter bars, and an RSI confirmation; neither is modelled here.
* Trading costs and slippage were not checked in the simulator's settings; they would hurt the short bar sizes most.
* It is one in-sample test on five large, mostly rising stocks. It says nothing about a different period.
* The agent can say SKIP on any setup, so the live system may behave differently from this mechanical rule.

## What is running

All four versions are live next to each other (`trend_pullback_long`, `_4h`, `_1h`, `_15m`), so the live evidence (every trigger and what followed it, every agent verdict, every closed trade) can be compared per bar size as it accumulates. The comparison is repeatable: `python scripts/compare_timeframes.py`.
