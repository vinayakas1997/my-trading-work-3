# Replay P&L Report — run-2026-07-06-2026-07-31-v2

- **Window:** 2026-07-06 → 2026-07-31 (20 trading days)
- **Tickers:** AAPL, TSLA, JNJ
- **Starting equity:** $100,000.00
- **Ending equity:** $99,760.42
- **Total P&L:** **$-239.58 (-0.24%)**
- **Trades executed:** 1

> Held positions are marked at the real historical daily close (fetched from `vinu-stock-price`), not the broker's own recorded `last_close` — the historical-fill broker only ever sets that field at fill time and never refreshes it on days without a new trade (confirmed bug, see `historical-fill-broker/test-log.md` Bug-2). Note this means the P&L below reflects the *true* price path, which the agent itself was never shown during the replay — the agent's own tool responses reported a flat, frozen mark the whole time.

## Standard Metrics (vinu_simulator.engine.metrics)

| metric | value |
| --- | --- |
| total_return | -0.0024 |
| sharpe_ratio | -0.2265 |
| max_drawdown | -0.0308 |
| win_rate | 0.5263 |
| cagr | -0.0313 |
| annual_volatility | 0.1135 |
| profit_factor | 0.9590 |
| sortino_ratio | -0.3148 |

## Trade Log

| date | symbol | side | qty | fill_price | cash_after |
| --- | --- | --- | --- | --- | --- |
| 2026-07-09 | AAPL | buy | 100.0 | 310.45 | 68,908.42 |

## Day-by-Day Decisions

| date | action | symbol | side | qty | tools used | reasoning excerpt |
| --- | --- | --- | --- | --- | --- | --- |
| 2026-07-06 | none | TSLA | — | — | get_portfolio, get_stock_price, get_features, get_fundamentals | TSLA shows significant volatility - it went from ~408 to a low of ~368, then rallied to ~424, but closed at 393.39 (a significant drop from the high). Let me ge |
| 2026-07-07 | none | AAPL | — | — | get_portfolio, get_stock_price, get_features | AAPL technicals: - Latest close: 308.43 - SMA20: 294.63 (price above SMA - bullish) - RSI14: 56.6 (neutral, slightly bullish) - MACD: not available yet  The sto |
| 2026-07-08 | trade | AAPL | buy | 100 | get_portfolio, get_stock_price, get_features, submit_order | ## Order Executed Successfully  **Trade Summary:** - **Symbol**: AAPL - **Action**: Buy 100 shares - **Fill Price**: $310.45 - **Total Cost**: $31,045.00 - **Re |
| 2026-07-09 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-09)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-10 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-10)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-13 | none | AAPL | — | 100 | get_portfolio | ## Current Portfolio Status (as of 2026-07-13)  **Account Summary:** - Total Equity: $99,953.42 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L:  |
| 2026-07-14 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-14)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-15 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-15)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-16 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-16)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-17 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-17)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-20 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-20)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-21 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-21)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-22 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-22)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-23 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-23)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-24 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-24)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-27 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-27)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-28 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-28)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-29 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-29)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-30 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-30)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |
| 2026-07-31 | none | AAPL | — | 100 |  | ## Current Portfolio Status (as of 2026-07-31)  **Account Summary:** - Total Equity: $100,000.00 - Cash: $68,908.42 - Market Value: $31,045.00 - Unrealized P&L: |

## Honesty Flags — direction-calling from proven-negative signals

_No day's trade decision leaned on sentiment / significance_score for a directional call._

---

*Generated 2026-08-03 04:36 UTC by scripts/report_month_replay.py — metrics from vinu_simulator.engine.metrics, not hand-rolled.*