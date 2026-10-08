# Handling system: portfolio allocator (plan)

Written 2026-10-08. Status: PLAN ONLY, nothing below is built yet except where the status column says so.

## 1. Why this exists

The Alpaca paper account holds about $96,000 of play money. The real money is about $20. Today the allocator sizes from the paper balance, so a paper-sized order says nothing about what $20 would do. Nothing records that money is already committed to an open trade, and nothing weighs "what if this trade fails or wins" before the next dollar is spent. This folder holds the plan for one separate component that fixes that.

## 2. Shape: a self-isolated entity

The allocator is a pure calculation. It reads no database, calls no service and holds no state. It gets numbers in and returns numbers out, so it can be tested with plain inputs and trusted to give the same answer twice.

```
inputs                                   outputs
  real_capital (e.g. 20.00)                per candidate: dollars, whole or fractional shares, reason
  committed (money in open trades)         free cash left
  reserve_fraction (e.g. 0.40)             reserve held back
  candidates: ticker, price, edge stats    refusals with reasons
  costs per session
  account_mode tag
```

A thin adapter outside the entity gathers the inputs from the book, research artifacts and the broker, and hands the result to portfolio-api. The entity itself never sees the paper balance as a capital base.

## 3. The money rules

1. **Capital base** is `real_capital`, a setting. Alpaca paper only supplies fills and prices.
2. **Free cash** = real_capital − committed − reserve. Committed is open positions at cost. A $1.76 trade leaves $18.24 before the reserve.
3. **Reserve** is a share of real_capital that is never allocated (the 40% idea). Default is set per decision, not hard-coded.
4. **No double-spend**: an allocation can never exceed free cash, and the order guard refuses an order above free cash.
5. **Lot constraint**: at $20 a single share of most stocks costs more than the whole account. The entity must know whether fractional shares are available for a ticker and drop candidates that cannot be bought with the free cash.

## 4. The maths (what decides the amount)

All of these are standard results; the plan is to use the simple, conservative form of each.

| Step | Method | Why |
|---|---|---|
| Edge per trade | expected return = p_win × avg_win − (1 − p_win) × avg_loss − costs | costs come from the session cost base (`session-cost-evidence.md`) |
| Honest p_win | Beta posterior (shrink the win rate toward 50% when there are few trades) | 30 trades is a thin sample; raw win rate flatters |
| Bet size | fractional Kelly (a quarter to a half of full Kelly), f = (b·p − q) / b | full Kelly is too aggressive for noisy edge estimates |
| Cap per trade | min(Kelly, max_position_pct, free cash) | the existing mandate caps still apply |
| Ruin check | scenario table: if this trade fails (lose avg_loss) and if it wins (gain avg_win), what is left and is the next best trade still affordable | the "if it fails / if it goes positive" step from the discussion |
| Ranking | order candidates by expected return per dollar after costs; fund from the top until free cash runs out | answers "which ticker is best for the next dollar" |
| Drawdown scale | keep the existing halve/flat/halt scale from the drawdown monitor | already built, applied to the real base |
| Paper to real | scale paper per-trade returns (percent, not dollars) to the real base | percent returns carry across account sizes, dollar figures do not |

Not built from theory alone: the thresholds (reserve share, Kelly fraction, ruin limit) are decisions for the user, not inventions. The plan proposes defaults and each is a setting.

## 5. Tagging: paper and real must never mix

Every record that carries money gets two tags: `account_mode` (`paper` or `real`) and `capital_base` (the figure the size was computed from).

| Place | Today | Needed |
|---|---|---|
| Order ledger (`scheduler_executions`) | no tag | `account_mode` column |
| Book positions and closed positions | no tag | `account_mode` column; open/closed queries filter on it |
| Allocation history (portfolio-api) | `reserve_fraction`, equity | add `account_mode`, `capital_base`, `committed` |
| Safety ledger | kill-switch events | `account_mode` on each event |
| Performance and feedback (reflection, research) | none | paper results are labelled paper; any real-money statistic is computed only from `real` rows |
| Dashboards and reports | one balance | show the two bases side by side, never summed |
| Mandate and order guard | one mandate | limits expressed against `real_capital` when mode is real |

Rule: a join or sum across the two modes is a bug. A guard test per table checks that queries filter by mode and that an empty mode is refused.

## 6. Implementation steps and status

| # | Step | Status |
|---|---|---|
| 1 | Setting `real_capital` and `account_mode` (env, validated, default paper) | not started |
| 2 | Pure allocator module with the maths above and unit tests on plain numbers | BUILT 2026-10-08, not wired in: `vinu-portfolio/vinu_portfolio/capital_allocator.py`, 15 tests in `tests/test_capital_allocator.py` |
| 3 | Capital ledger: committed money from open positions, free cash, refusal above free cash | not started |
| 4 | Tag columns and mode filters (order ledger, book, allocation history, safety ledger) | not started |
| 5 | Adapter in portfolio-api: gathers inputs, calls the entity, uses the allocator `amount` per artifact (closes O20) | not started |
| 5b | Read-only allocator summary (free cash, committed, scenario table, tagged results) that the agent reads; nothing is pushed to it | not started |
| 6 | Order guard: refuse orders above free cash in real mode | not started |
| 7 | Scenario table (fail / win) in the allocation response, so the user sees the reasoning | not started |
| 8 | Paper-to-real scaling and a report that shows both bases | not started |
| 9 | Live drill on paper with `real_capital` = 20 (sizes small, committed money tracked) | not started |

Already in place and reused: reserve fraction setting (default 0, `vinu-portfolio`), drawdown scale-down, mandate caps (`max_position_pct`, `max_order_value`), session cost base, the book and its fill write-back (P33).

## 7. Open decisions for the user

1. Reserve share: 40%, or another figure, and is it a share of real capital or of free cash?
2. Kelly fraction: a quarter, a half?
3. Fractional shares: does Alpaca allow them for the tickers in use, and is that the way to trade $20?
4. Real trading: when it starts, is it a separate broker account (so the paper account stays untouched), or a second mode on one system? The tagging above works for either.
