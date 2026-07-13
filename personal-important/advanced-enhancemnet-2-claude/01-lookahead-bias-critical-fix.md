# Enhancement 1: Fix Look-Ahead Bias in the Backtest Engine

## Current State Score: 2/10 — this is the single highest-priority fix in the whole codebase

Look-ahead bias means a backtest uses information that would not have been available at the time a trading decision was actually made. It is the #1 cause of backtests that look great and then fail in live trading, because the "edge" the backtest measured was partly made of future information the live strategy will never have. Two separate leaks were found.

## Leak 1: `bfill()` in the LLM-generated-strategy execution path

`vinu-components/vinu-simulator/vinu_simulator/engine/custom_sim.py:91`:

```python
price_matrix = price_matrix.ffill().bfill()
```

`.bfill()` (backward-fill) propagates a *future* price backward to fill gaps — including the gap before a symbol's first available trading day. Any date before a symbol started trading, or any hole in the middle of the series, gets filled with a price that didn't exist yet at that point in time.

This exact bug was found and fixed once already. `vinu_simulator/engine/simulator.py` (the original/default backtest path) no longer calls `.bfill()` — per the commit history and `docs/book/issue-plan-summary/20260706-summary-1.md:27-29`, it was deliberately removed there. **The fix was never applied to `custom_sim.py`**, which is the path used for LLM-generated and ad-hoc user strategy code (`POST /simulate/custom`, referenced throughout `how-it-works.md` as the actual execution route for every strategy the research loop produces). So the one execution path most likely to run arbitrary/novel code is also the one still leaking future prices into the past.

### Fix

```python
# vinu_simulator/engine/custom_sim.py:91
price_matrix = price_matrix.ffill()  # forward-fill only — never let future data flow backward
# Any remaining NaN (before a symbol's first trade) should raise or be excluded,
# not silently filled — same as simulator.py already does.
if price_matrix.isna().any().any():
    missing = price_matrix.columns[price_matrix.isna().any()].tolist()
    raise ValueError(f"No price data before first available date for: {missing}")
```

Same audit for `volume_data` fill logic nearby (`custom_sim.py:95`, currently `fillna(0.0)`) — zero volume is a defensible default (see [03](03-cost-model-wiring-and-bugs.md) for why zero volume silently zeroing out market impact is itself a separate bug), but confirm no `bfill()` is hiding there too.

## Leak 2: Same-bar signal and execution price, with no engine-level guard

`vinu_simulator/engine/simulator.py:98-109`:

```python
for step_idx, date in enumerate(total_calendar):
    prices = price_data.loc[date].values.astype(np.float64)
    ...
    target_weights = ws_aligned.loc[date].values.astype(np.float64)
```

Both the execution price and the target weight signal are read from the **same** `date`. If a strategy's `generate_weights()` computes its signal using that day's own close (e.g., "if close > SMA(20) of closes including today"), the backtest fills the trade at the exact price the signal was computed from — a trade that, in reality, could not happen (you cannot know the closing price until the close has happened, at which point the market for that session is over).

Nothing in the strategy interface (`BaseStrategy`, referenced in `how-it-works.md` section 6) or the engine prevents this. It is left entirely to strategy authors — including the LLM generator — to self-enforce causality, which they have no reason to do since nothing in the interface, the AST validator, or the sandbox exec check (`llm_generator.py` validation pipeline) inspects for it.

### Fix — two layers

**Layer 1 (mandatory, engine-level):** Shift execution by one bar. Signals computed on bar N execute at bar N+1's open (or N+1's close, if the strategy is documented as close-to-close), never at bar N's close.

```python
# simulator.py — decide weights using data through `date`, but only apply/price the trade
# using the NEXT trading day's data.
signal_dates = total_calendar[:-1]
execution_dates = total_calendar[1:]

for signal_date, exec_date in zip(signal_dates, execution_dates):
    target_weights = ws_aligned.loc[signal_date].values.astype(np.float64)  # decided using data up to signal_date
    prices = price_data.loc[exec_date].values.astype(np.float64)           # filled at the next bar
    ...
```

This changes result numbers for every existing template and every past backtest — that is expected and correct; the old numbers were optimistic.

**Layer 2 (defense-in-depth, generator-level):** Add a static check to the LLM code validator (`llm_generator.py`'s `validate_code()`) that flags — not blocks, since static analysis can't fully prove causality — strategies whose `generate_weights()` indexes the *last* row of the input `data` frame for anything other than reading (i.e., warn if the function reads `data.iloc[-1]` and that value visibly feeds the return weights without an explicit shift). This won't catch everything, but it catches the common LLM failure mode of "use today's close to decide today's trade."

## Why This Is Priority 0

Every other enhancement in this folder — walk-forward gating, cost model wiring, benchmark comparison — computes statistics *on top of* the numbers this engine produces. If the underlying P&L series already contains future information, none of those statistics mean what they claim to mean. Fix this first; every other doc in this folder assumes it's fixed.

## Code Changes Summary

| File | Change | Description |
|---|---|---|
| `vinu_simulator/engine/custom_sim.py:91` | MODIFY | Remove `.bfill()`, raise on leading NaN instead of silently filling |
| `vinu_simulator/engine/simulator.py:98-118` | MODIFY | Shift execution to `date[i+1]` relative to signal at `date[i]` |
| `vinu_simulator/engine/custom_sim.py` | MODIFY | Apply the same T+1 shift as `simulator.py` (confirm it currently mirrors the same-bar behavior) |
| `llm_generator.py` (validator) | MODIFY | Add heuristic same-bar-usage warning, surfaced in candidate metadata |
| `tests/test_simulator.py` | NEW | Golden test: construct a price series where same-bar execution and T+1 execution produce different, hand-computed P&L; assert the engine returns the T+1 number |
| `tests/test_custom_sim.py` | NEW | Test that a leading-NaN symbol raises rather than silently back-filling |

## Complexity & Verdict

- **Difficulty:** Low-medium. The shift itself is a small, mechanical change; the hard part is updating every test that currently encodes the same-bar numbers as "correct."
- **Priority:** **P0 — blocks trusting any other metric in the system.**
- **Risk of not fixing:** Every strategy the system has ever "approved" (`*_approved.py`) should be treated as unvalidated until re-run through the corrected engine.
- **Time estimate:** 2-3 days including test updates.
