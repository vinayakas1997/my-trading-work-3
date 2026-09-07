# Deep Dive — nautechsystems/nautilus_trader (28.6K stars)

> Source: `https://github.com/nautechsystems/nautilus_trader` — deterministic, fills, catalog.

## What to look at

- `crates/model/` — fill model (slippage + queue position), latency model, book model.
- `nautilus_trader/persistence/catalog/` — Parquet catalog with versioning/lineage.
- `examples/` — research→live parity examples.

## Clone & inspect

```bash
git clone https://github.com/nautechsystems/nautilus_trader --depth 1
ls crates/model/src/
```

## Extractable for Vinu

1. **Fill/latency/book models** → harden `vinu-simulator/engine/costs.py:73` AlmgrenChriss with queue position + spread; add latency to `simulator.py:103` T+1.
2. **Catalog + lineage** → `vinu-infra/` freeze manifest `assets/` (adoptable Row 21) — hash of `data/news:stock-price:features`.
3. **Deterministic core** → ensure `vinu-simulator` + `vinu-live` replay same event order (nanosecond tick).

## Test pattern

- Nautilus `tests/test_fills.py` — assert partial fill when volume < order size * max_pct_of_volume.
