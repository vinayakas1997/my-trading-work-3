# Plan - 19 Portfolio Inside

Goal: Safe weights: DD de-risk + per-symbol regime first.

Files touched:
- `vinu-components/vinu-portfolio/service.py:53,232,288,347,385,393,486,505` parity/build/composition/tilt/regime/alloc/cache.
- `vinu-components/vinu-portfolio/config.py:53,170` bounds + recompute.
- `historical_simulation.py:94` walk-forward + allocator_compare notebook.

Steps:
1. Composition action cap 20% + tilt tune after 30 trades.
2. DD halve 10% flat 15% + per-symbol regime + prob blend + high_vol de-risk.
3. Sleeves 1D/1H + regime cov + hysteresis 2d.
4. HRP/L2/BL + NCO/CVaR + blend compare after 4 guards + live 60d.

Knobs: COMPOSITION_ACTION, TILT_BOUND, DD_HALVE/FLAT, SLEEVES, PER_SYMBOL_REGIME, BLEND, HIGH_VOL_DE_RISK (see 10).
Acceptance: overweight capped, DD halves, per-symbol differs SPY, no flip-flop.
