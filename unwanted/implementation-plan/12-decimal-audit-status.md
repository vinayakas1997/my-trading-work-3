---
task: 12-decimal-audit.md
status: complete
---

# Status: task 12 — audit and fix float-vs-Decimal precision on the real money path

## The answer to the audit question

**YES, a real gap existed.** The order-quantity and cash-ledger path used raw `float` arithmetic end to
end:

- `vinu-live/vinu_live/signal_translator.py` — `_build_instruction` computed `target_qty = target_value /
  price`, `delta = target_qty - current_qty` in float and emitted fractional share quantities.
- `vinu-live/vinu_live/execution.py` — `plan_twap` / `plan_vwap` sliced order quantities with
  `round(..., 4)` in float.
- `vinu-live/vinu_live/book/positions.py` — the ledger: `add_to_position` (weighted-average cost basis),
  `reduce_position` / `close_position` (realized PnL), `daily_realized_pnl` (sums realized PnL) all in
  float, stored in SQLite `REAL` columns.

The float usages that are fine and were left alone: config thresholds
(`VINU_PORTFOLIO_*` parsing), target weights, exposure monitoring (`book/exposure.py` — limit/threshold
comparison), and statistical analytics (Sharpe/volatility/regime). No conversion there, per the plan's
no-over-conversion rule.

## What I did

- **`vinu-live/vinu_live/book/quantize.py`** — NEW: the single documented rounding rule for the money
  path. `to_decimal()` (float → `Decimal(str(x))`, so `0.1` stays `Decimal("0.1")`), `quantize_qty`
  (whole shares by default, `VINU_LIVE_SHARE_PRECISION` for fractional-share brokers, ROUND_HALF_UP),
  `floor_qty` (ROUND_DOWN for slicing so remainders fold correctly), `quantize_money` (cents,
  ROUND_HALF_UP), `qty_float`/`money_float`, and `sum_money` (drift-proof exact sum).
- **`book/positions.py`** — `open_position`/`add_to_position`/`reduce_position`/`close_position` now do
  their arithmetic in Decimal, quantize order quantities to whole shares and money (prices, commissions,
  realized PnL) to cents on every write, and `daily_realized_pnl` sums through `sum_money`. The average
  entry price stays **Decimal-exact** (not cents-truncated) — a truncated cost basis would scale into
  real money error over many shares. SQLite columns stay `REAL` (no schema migration): every stored
  value is the float nearest an already-quantized Decimal and round-trips exactly through
  `Decimal(str(x))`.
- **`signal_translator.py`** — `_build_instruction` computes target/delta/quantity in Decimal, emits a
  whole-share `qty` (never a `5.2500000000001`-style share count), and skips a delta that quantizes to
  zero shares.
- **`execution.py`** — `plan_twap` / `plan_vwap` slice in Decimal: intermediate slices `floor_qty`,
  remainder folded into the final slice, so slice quantities are whole shares and always sum **exactly**
  to the order quantity.
- **`vinu-live/tests/test_decimal_money.py`** — NEW regression suite (14 tests): the exact drift
  scenario through the real ledger path (three 0.10 realizations sum to exactly `0.3`, where pure float
  yields `0.30000000000000004`), commission math, non-truncated cost basis, whole-share order emission,
  zero-quantity skip, and exact-slice-sum guarantees (including `100 / 6` and `1 / 10`).

## Testing

- Full `vinu-live/tests`: **170 passed** (156 existing + 14 new) — existing tests untouched and green
  (one existing `test_add_to_position` tolerance now passes even more comfortably since the cost basis is
  Decimal-exact).

## Alignment with plan / acceptance criteria

- Clear documented answer: the money path was float and now is Decimal; the analytics float usage was
  confirmed fine and left alone ✓
- The specific money-handling code converted to Decimal with an explicit rounding/quantization rule
  (whole shares / cents), with a regression test proving the `0.1 + 0.2`-class drift is now exact
  through the real ledger path ✓
- No unnecessary conversion of legitimately-float analytics ✓

## Notes / deliberate choices

- Storage stays `REAL` with quantized writes (no migration, no pandas/numpy interop friction) — the
  plan's "don't over-convert" guidance. If the broker ever needs sub-cents cost-basis or per-fill money,
  that's a schema change; the arithmetic layer is already Decimal.
- `VINU_LIVE_SHARE_PRECISION` defaults to whole-share trading; fractional-share brokers just set it.