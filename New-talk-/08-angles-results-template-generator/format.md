# Angle fact sheet — agreed format (built, see 01-implementation.md)

One block like this per (angle, symbol). Self-contained — no other
document needed to understand it. Two parts: a short paragraph (what the
angle is, its real fixed condition, real data source), then a table
(market session x time format, real results with sample size). Nothing in
either part compares, ranks, or judges — every cell states real values
with their `n`, or `not available` when that combination has no real
stored run yet.

---

**arima (AAPL):** ARIMA — AutoRegressive Integrated Moving Average — fits
an equation to a stock's own past closing prices and forecasts the single
next closing price, plus a range it is 95% confident the real price will
land inside. No machine learning, no pretraining — refit from scratch at
every step. Condition: N=100 candles of history considered before each
forecast (fixed rolling window, not expanding — and "100 candles" means
100 candles *at that column's own resolution*: 100 one-minute candles for
the `1min` column, 100 daily candles for the `1D` column, not a fixed
100-minute window applied to every column). Real data: AAPL, Alpaca feed.
Table columns = candle/bar time resolution (how much real time each row
of underlying price data spans before ARIMA sees it). `hit_rate` in the
table below = the fraction of steps where the real next closing price
actually landed inside that step's own predicted 95% confidence interval
(not a direction guess, not "price went up/down correctly" — purely
whether the real price fell inside the stated range). `n` = how many real
steps that fraction is based on.

All times below are UTC. Session row labels, as fixed UTC hour ranges
(New York shifts with US daylight saving; London/closed do not):

- `closed` = 00:00–07:00 UTC
- `london` = 07:00–13:00 UTC
- `ny_premarket` = 13:00–13:30 UTC (DST) / 13:00–14:30 UTC (non-DST)
- `ny_regular` = 13:30–20:00 UTC (DST) / 14:30–21:00 UTC (non-DST) — NYSE's 9:30am-4:00pm ET regular trading hours
- `ny_afterhours` = 20:00–24:00 UTC (DST) / 21:00–24:00 UTC (non-DST)

| session | 1min | 5min | 15min | 1H | 4H | 1D |
|---|---|---|---|---|---|---|
| closed | not available | not available | not available | not available | not available | hit_rate=0.96 (n=100), computed_at=2026-08-09T08:49 UTC, run_id=1c95db56965a |
| london | not available | not available | not available | not available | not available | not available |
| ny_premarket | not available | not available | not available | not available | not available | not available |
| ny_regular | not available | not available | not available | not available | not available | not available |
| ny_afterhours | not available | not available | not available | not available | not available | not available |

_For anything about this run beyond this table, call
`GET /v1/stage1/vinu-initial-analysis/fetch/AAPL/1D/{time_range}/arima/1c95db56965a`
(the real API route, `{time_range}` filled in with whatever window you
need). This document states values only — it does not compare, rank, or
advise between them._
