# Deep Dive — polakowo/vectorbt (9.0K stars)

> Source: `https://github.com/polakowo/vectorbt` — vectorized sweep, PRO+OSS hybrid.

## What to look at

- `vectorbt/generic/` — `vbt.MA.run(price, window)`, `ma_crossed_above`.
- `vectorbt/portfolio/` — `Portfolio.from_signals`, `total_profit`, QuantStats.
- `examples/` — `colab` notebook: `fast_window × slow_window × symbol` matrix.

## Clone & inspect

```bash
pip install -U "vectorbt[full]"  # or rust variant
python -c "import vectorbt as vbt; print(vbt.__version__)"
```

## Extractable for Vinu

1. **Vectorized sweep** → replace per-candidate `run_sweep_candidate` `sweep.py:159` loop with matrix broadcast: `fast_window × slow_window × symbol` → seconds not minutes. Covers pending Row 7 tuning + Row 1 rehearsal speed.
2. **Signal ranking/mapping** → adoptable Row 22 — distribution view of idea crowding.
3. **Indicator ecosystem** — TA-Lib/Pandas-TA bridge for 31-angle expansion.

## License note

Fair-Code Apache 2.0 with Commons Clause — OSS free, commercial sale of primarily-this-software needs exception.
