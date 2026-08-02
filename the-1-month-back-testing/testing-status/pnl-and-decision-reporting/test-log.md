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

_Nothing logged yet — implementation has not started._
