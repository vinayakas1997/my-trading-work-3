# Deep Dive — microsoft/Qlib (48.4K stars)

> Source: `https://github.com/microsoft/qlib` — PIT DB, Alpha360, RD-Agent. Relevant to pending Row 15 (universe/PIT) and Row 11 (Thesis Intake).

## What to look at

- `qlib/data/` — Point-in-Time database (`pull/343 Mar 2022`), handler, processor.
- `examples/tutorial` — notebook end-to-end (data → factor → model → backtest → attribution).
- `RD-Agent` — `https://github.com/microsoft/RD-Agent` — LLM autonomous factor/model evolution.

## Clone & inspect

```bash
git clone https://github.com/microsoft/qlib --depth 1
ls qlib/data/  # handler, storage, provider
cat qlib/data/README.md
```

## Extractable for Vinu

1. **PIT contract** → `vinu-initial-analysis/quarters.py` tier2 window + `vinu-stock-price` store. Guarantees no future release used past. Fixes `VINU_STAGE1_START_DATE` determinism `pending Row 15`.
2. **Handler/processor** → `vinu-tools` feature pipeline; Alpha360 as angle example for 31-angle set.
3. **RD-Agent loop** → pattern for `Thesis Intake` `strategy-definitions` generation (Row 11) — not copy code, copy loop spec.

## Test pattern to borrow

- PIT `test_*pit*.py` — asserts as-of join, no leakage across embargo.
