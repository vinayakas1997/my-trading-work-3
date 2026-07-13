# Enhancement 3: Flip the Cost Model Default, Fix the Zero-Volume Bug, Add Risk-Free Rate and Borrow Cost

## Current State Score: 6/10 — the hard part (Almgren-Chriss) is built and correctly wired to both live API routes; it's just off by default

Round 1's `08-slippage-market-impact.md` proposed building an `AlmgrenChrissCostModel`. That work happened — `vinu_simulator/engine/costs.py:57-108` — and it's a reasonable implementation of volume-scaled market impact, and (verified below) it's reachable from both `POST /simulate` and `POST /simulate/custom` via `WeightSimulator._build_cost_model()`. The problem is narrower than first thought: **it's wired correctly but defaults off**, plus two separate real bugs (zero-volume handling, missing risk-free rate / borrow cost) that are independent of the wiring question.

## Bug 1 (corrected after verification): Almgren-Chriss is properly wired in the live path — but defaults off, and a dead legacy class still hardcodes flat

**Correction to the original pass of this audit:** the first version of this doc claimed `SimulatorEnv` hardcoding `FlatCostModel` was the live default for every backtest. That was checked against the wrong class. Tracing the actual request paths:

- `POST /simulate` → `service.py:93` → `WeightSimulator(sim_config)`
- `POST /simulate/custom` (the path LLM-generated and ad-hoc strategies run through) → `custom_sim.py:108` → `WeightSimulator(sim_config)`

`WeightSimulator.__init__` (`simulator.py:27-43`) correctly reads `config.slippage_model` and selects between `AlmgrenChrissCostModel` and `FlatCostModel` — this selector is real and both live API routes go through it. **So Almgren-Chriss is not dead code and is reachable from every backtest today.**

The actual (smaller) issue: `SimulationConfig.slippage_model` (`models/simulation.py:18`) **defaults to `"flat"`**, so unless a caller explicitly sets `slippage_model="almgren_chriss"`, every backtest still gets flat-percentage costs by default — same practical outcome (illiquid names underpriced on cost) as originally described, but the fix is a one-line default change, not new wiring.

Separately, `SimulatorEnv` (`simulator.py:237-250`) — a **different class from `WeightSimulator`**, used only by `tests/test_simulator.py`, never by `service.py` or `custom_sim.py` — does still hardcode `FlatCostModel` unconditionally, ignoring config entirely. This has no effect on live backtests, but it means the test class and the production class can silently diverge in cost behavior, which is worth cleaning up so a future test written against `SimulatorEnv` doesn't give a false sense of what production does.

### Fix

```python
# models/simulation.py:18 — flip the default
slippage_model: str = "almgren_chriss"  # was "flat"; flat now requires explicit opt-in
```

```python
# simulator.py:247-250 — SimulatorEnv should reuse the same selector WeightSimulator already has,
# instead of a second hardcoded construction, so the two classes can't diverge
class SimulatorEnv:
    def __init__(self, tickers, price_data, config: SimulationConfig):
        ...
        self._cost_model = WeightSimulator(config)._build_cost_model()  # or extract _build_cost_model to a free function both classes call
```

If `SimulatorEnv` is legacy/superseded by `WeightSimulator` entirely, the cleaner fix is deleting it and repointing its tests at `WeightSimulator` — confirm with whoever owns this code before removing a class with 5 existing tests against it.

## Bug 2: Missing volume data silently produces zero market impact

`costs.py:71-73`: when volume is missing or zero, the impact term is forced to `0`. Separately, `custom_sim.py:95` fills any missing volume with `0.0` before the cost model ever sees it. The combined effect: **a data gap in volume makes the simulator believe a trade had zero market impact**, which is the most favorable possible (and wrong) assumption — it should be the opposite. Missing liquidity data is evidence of *higher* uncertainty/risk, not proof of a costless fill.

### Fix

```python
# costs.py — when volume is missing/zero, apply a conservative penalty instead of zero impact
if volume is None or volume <= 0:
    # No liquidity data → assume worst-case thin-liquidity impact, not zero.
    impact = self.config.missing_volume_impact_pct  # e.g. 0.005 (50bps), configurable
else:
    participation_rate = (shares * price) / (volume * price)
    impact = self._temporary_impact_coeff * (participation_rate ** 0.5)
```

Flag this in the risk critic too: a strategy whose backtest relied on symbols/dates with missing volume data should surface that as a caveat in the report (`report.py`), since the cost estimate for those trades is a placeholder, not a measurement.

## Bug 3: No risk-free rate, anywhere

`simulator.py:219` hardcodes `risk_free_rate=0.0` into every Sharpe/Sortino computation. `SimulationConfig` (`models/simulation.py:11-21`) has no field for it at all — this isn't a default that's wrong, it's a parameter that doesn't exist. Sharpe ratios computed this way are systematically inflated relative to the standard definition (excess return over risk-free, divided by volatility) whenever the risk-free rate is meaningfully above zero, which it has been for most of the last several years.

### Fix

```python
# models/simulation.py
@dataclass
class SimulationConfig:
    ...
    risk_free_rate_annual: float = 0.0  # explicit, overridable; document that 0.0 is a simplification, not a fact
```

```python
# simulator.py:219
sharpe = compute_sharpe(returns, risk_free_rate=config.risk_free_rate_annual / 252)
```

This alone won't change strategy rankings much in relative terms (all strategies get the same treatment), but it matters a great deal the moment this system's numbers are compared to anything external — a benchmark, a target hurdle rate, or a real fund's reported Sharpe.

## Bug 4: Short positions have no borrow cost

`allow_short` defaults to `True` (`models/simulation.py:20`) and the engine removes the sell-size cap when it's on (`simulator.py:137-138`), but a grep across the entire repo for `borrow`/`margin`/`locate` returns zero matches. Every short position in every backtest is modeled as free leverage — no stock loan fee, no hard-to-borrow premium, no margin interest on the cash proceeds sitting uninvested. For any strategy that shorts meaningfully, this overstates returns.

### Fix (minimum viable, not a full margin engine)

```python
# costs.py
BORROW_COST_ANNUAL_DEFAULT = 0.0075  # 75bps/yr, generic easy-to-borrow assumption; configurable per symbol later

def daily_borrow_cost(short_notional: float, annual_rate: float = BORROW_COST_ANNUAL_DEFAULT) -> float:
    return short_notional * annual_rate / 252
```

Applied as a daily drag on any negative holding, charged into the same P&L accounting path as transaction costs. This doesn't need per-symbol accuracy to be useful — even a flat, generic borrow assumption is far closer to reality than the current implicit zero.

## Code Changes Summary

| File | Change | Description |
|---|---|---|
| `vinu_simulator/models/simulation.py:18` | MODIFY | Flip `slippage_model` default from `"flat"` to `"almgren_chriss"` (selector logic already correct in `WeightSimulator._build_cost_model()`) |
| `vinu_simulator/engine/simulator.py:237-250` | MODIFY | `SimulatorEnv` (test-only class) should reuse `WeightSimulator._build_cost_model()` instead of its own hardcoded `FlatCostModel`, so it can't silently diverge from production behavior |
| `vinu_simulator/engine/costs.py:71-73` | MODIFY | Missing/zero volume → conservative impact penalty, not zero |
| `vinu_simulator/models/simulation.py` | MODIFY | Add `risk_free_rate_annual` field; add `slippage_model` default → `"almgren_chriss"` |
| `vinu_simulator/engine/simulator.py:219` | MODIFY | Use `config.risk_free_rate_annual` instead of hardcoded `0.0` |
| `vinu_simulator/engine/costs.py` | MODIFY | Add `daily_borrow_cost()`, apply to short holdings each day |
| `report.py` | MODIFY | Surface a "missing volume data" caveat when any traded date lacked volume |
| `tests/test_costs.py` | NEW | Test missing-volume path produces a penalty, not zero; test borrow cost accrues on short holdings |

## Complexity & Verdict

- **Difficulty:** Low. Every piece except borrow cost is a wiring fix to code that already exists and is already tested in isolation (`advanced-enhancement/08-slippage-market-impact.md` verdict called this "medium," but that was for building Almgren-Chriss from scratch — it's already built).
- **Priority:** **P1** — do this after [01](01-lookahead-bias-critical-fix.md) and [02](02-overfitting-and-walkforward-gating.md), since cost realism only matters once the underlying signal timing and validation methodology are sound.
- **Risk:** Very low — these changes only make costs more conservative/realistic, so they can't introduce new look-ahead or leakage issues.
- **Time estimate:** 2-3 days.
