# Deep Dive — freqtrade/freqtrade (54.1K stars)

> Source: `https://github.com/freqtrade/freqtrade` — hyperopt, lookahead, dry-run.

## What to look at

- `freqtrade/optimize/` — hyperopt with Bayesian `skopt`/`hyperopt`.
- `freqtrade lookahead-analysis` + `recursive analysis` — flags use of same-bar close to enter.
- `freqtrade/dry_run_wallet.py` — wallet-level simulated fills tick-by-tick.

## Clone & inspect

```bash
git clone https://github.com/freqtrade/freqtrade --depth 1
freqtrade lookahead-analysis --help  # after pip install -e .
grep -r "lookahead" freqtrade/ --include="*.py" | head
```

## Extractable for Vinu

1. **Lookahead guard** → add test analogous to `vinu-simulator/tests/test_custom_sim.py:98 TestPerfectForesightCannotProfit` but as post-sweep scan on winning strategy's `generate_weights`. Covers pending Row 1.
2. **Pairlist filter** → before `Gate` `04:23` prune illiquid tickers (vol/volume). Saves LLM cost.
3. **Dry-run wallet** → extend `shadow_evaluator.py:23` Sharpe-only to wallet trades/fees (adoptable Row 24).

## Test pattern

- `freqtrade/tests/test_lookahead.py` style: assert strategy fails if uses `data[i+1]` in `data[i]`.
