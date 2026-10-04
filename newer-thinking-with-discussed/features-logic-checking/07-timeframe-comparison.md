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

---

## Why 15-minute and 1-hour were so bad (measured, 2026-10-04)

Three suspects, tested one by one:

1. **Bad tickers? No.** All five stocks lost at 15 minutes (-33% to -62%), and all five rose over the same years (buy and hold +48% to +139%). It is not one unlucky stock.
2. **Bad strategy? Yes, on short bars. Mostly: no edge, then costs.**
   * Measured directly (no simulator, no costs): after a setup, the next 20 bars return +0.032% on 15-minute bars against +0.057% after *any* bar. That is no edge (-0.03%). On 1-hour bars +0.174% against +0.213% (-0.04%). On 4-hour +0.708% against +0.654% (+0.05%) and daily +1.727% against +1.612% (+0.12%); both small, noisy, and carried by 2-3 stocks.
   * The simulator charges 0.10% commission plus 0.05% slippage per side (about 0.30% per round trip), plus a market-impact model. Re-run with costs set to zero:

| Bar size | Sharpe with costs | Sharpe, free trading | Return with costs | Return, free trading |
|---|---|---|---|---|
| 15 minutes | -2.95 | **-0.49** | -45% | **-12%** |
| 1 hour | -0.22 | **+0.34** | -17% | **+21%** |
| 4 hours | +0.25 | +0.40 | +27% | +54% |
| 1 day | +0.34 | +0.39 | +42% | +49% |

   15-minute: costs caused about three quarters of the loss, and it still loses for free (no edge). 1-hour: a mildly profitable pattern that costs turn into a loser. 4-hour and daily: few trades, so costs matter little.
3. **Was the system's own analysis wrong? The measuring was right, the explaining was missing.** The numbers agree (raw forward returns and the simulator tell the same story). But the system only reported a Sharpe and a list of failed tests; it never said *why*. That gap is now closed: `vinu_research/failure_diagnosis.py` re-runs the best attempt of any run where nothing passed with and without costs and says which it is (`no_edge`, `edge_eaten_by_costs`, `works_after_costs`), flags results built on fewer than 30 trades, and states whether the rejection came from the validation tests instead. It is appended to the run report, the stored summary and the API response (`diagnosis`). Rules and numbers are tested against the table above (`tests/test_failure_diagnosis.py`, `tests/test_run_explains_failure.py`).

Not yet built: running the same diagnosis across several tickers at once (`diagnose_across` exists and is tested, but nothing calls it yet), and feeding the verdict back to the idea generator so it stops proposing short-bar versions of an idea that showed no edge.
