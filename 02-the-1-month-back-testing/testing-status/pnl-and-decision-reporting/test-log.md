# pnl-and-decision-reporting — Test Log

## What will be tested / Expected output

- Headline P&L number that is internally consistent with the trade log
  (sum of trade-level P&L reconciles with starting-vs-ending account
  equity).
- Metrics computed via the actual `vinu_simulator.engine.metrics` call
  (not a hand-rolled reimplementation), spot-checked against one
  hand-computed data point.
- A report readable top-to-bottom by a non-technical reader: what
  happened, whether it made money, and whether anything looked like it
  was cheating (lookahead, direction-calling from a proven-negative
  signal).
- Full detail: [../../scope-responsibilities/04-pnl-and-decision-reporting.md](../../scope-responsibilities/04-pnl-and-decision-reporting.md)

## Bug / Fix Log

### Verification results (2026-08-03) — `report_month_replay.py` against `run-2026-07-06-2026-07-31-v2`
- Script already existed (built during the earlier, pre-fix run;
  `scripts/report_month_replay.py`) and reused `vinu_simulator.engine.metrics
  .compute_full_metrics` as scoped — no hand-rolled Sharpe/drawdown.
- **Bug found — action-label false positives:** the day-by-day narrative's
  `action` column showed `trade` on almost every day, including pure
  no-tool-call status reports. Root cause: `run_month_replay.py::_parse_
  action`'s sell-word regex matched the bare word `close`, which fires on
  ordinary phrases like *"Latest close: 308.43"*. **Fixed**: tightened the
  buy/sell regexes to require an actual trade phrase (`bought`, `close the
  position`, etc.), tightened `qty` to require "N shares" instead of any
  bare number (was matching the `2026` in dates). Regenerated all 20 days'
  `response.json` summaries from the already-captured `final_content` (no
  LLM re-run needed) — now correctly shows exactly 1 `trade` day
  (2026-07-08) instead of 18 false positives.
- **Bug found — headline P&L was not real mark-to-market:** cross-referenced
  against `historical-fill-broker/test-log.md`'s Bug-2 (broker's
  `last_close` frozen at fill price, never refreshed). The original report
  showed a flat `-$46.58 (-0.05%)` for the whole month, which is just the
  entry slippage — it silently absorbed the broker's stale mark instead of
  catching it. **Fixed** at the reporting layer (not the broker, which is a
  separate, deferred fix): `_equity_curve()` now fetches real historical
  daily closes directly from `stock-api` and marks held positions against
  those, falling back to the broker's own value only if that fetch fails.
  Corrected result: **-$239.58 (-0.24%)**, Sharpe -0.23, max_drawdown
  -3.08%, win_rate 52.6%, annual_volatility 11.35% — materially different
  from, and more honest than, the pre-fix flat numbers.
- **Reconciliation check (the item's own "expected output" bar):** ending
  equity ($99,760.42) = cash ($68,908.42, from the broker's real ledger,
  unaffected by the mark-to-market fix) + 100 AAPL shares × $308.52 (the
  real 2026-07-31 close) = $68,908.42 + $30,852.00 = $99,760.42. Reconciles
  exactly.
- **Report includes an explicit note** (in `report.md` itself, not just
  this log) explaining the mark-to-market correction and that the agent's
  own tools never showed it this real price path — a direct "honesty flag"
  per the item's spec, surfaced to a reader of the report itself, not
  buried only here.
- **Trade log / P&L reconciliation**: 1 real fill (100 AAPL @ $310.45,
  filled T+1 on 2026-07-09 per the historical broker's no-lookahead
  discipline), cash decreased by $31,091.58 (cost including the
  Almgren-Chriss slippage/fee model, not just raw notional) — matches the
  ledger exactly.
- **Status:** item 4 verified working end-to-end against a real run, with
  two real bugs found and fixed during verification (see above; full code
  detail cross-referenced in `day-stepper-replay-harness/test-log.md` and
  `historical-fill-broker/test-log.md` to avoid duplication).
