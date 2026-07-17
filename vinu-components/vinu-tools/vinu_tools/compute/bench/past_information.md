# Bench — Structure History

## 2026-07-17: Reorganized

### What moved
- `compute/alpha_bench.py` → merged into `bench/runner.py`
- `compute/factor_backtest.py` → merged into `bench/backtest.py`
- `compute/decay/backtest.py` → merged into `bench/decay.py`

### Why
- All bench logic in one directory instead of split across compute/ root
- Re-export stubs replaced with actual implementations

### Old files (deleted)
- `compute/alpha_bench.py`
- `compute/factor_backtest.py`
- `compute/factor_decay.py`
