# Task 2: Live Metrics

**Status:** DONE

## Purpose

Compute the metric dict a frozen plan's rules are evaluated against
(`drawdown_pct`, `unrealized_pnl_pct`, `gap_against_position_pct`, `realized_vol_ratio`,
`realized_move_vs_forecast_std`, `shock_cluster_correlation`) from an open `Position` (Phase 3),
the current price, and the frozen plan's own `risk_bands`/`forecast`.

## Approach

- Pure/synchronous (`compute_live_metrics`) — all HTTP fetching (recent price history,
  shock-cluster correlation) happens in `orchestrator.py` and is passed in, keeping this module
  trivially testable with no network concerns.
- `drawdown_pct` proxies peak-to-current drawdown with decline-from-entry (`max(0, -pnl_pct)`)
  since the schema has no stored high-water-mark — exact at position open, conservative
  (never understates risk) afterward; documented as a known approximation, not silently
  assumed precise.
- `realized_vol_ratio` recovers Phase 4's GARCH-forecast vol by inverting
  `risk_bands.volatility_band_upper` (`_build_risk_band` set it to `vol * 1.5`) rather than
  re-fetching/recomputing Phase 1's forecast — reuses `vinu_tools.compute.risk.volatility.
  realized_volatility` for the live side (`vinu_tools` is explicitly cross-environment shared
  library per Phase 1's doc, unlike `vinu_research.models`).
- Every metric is **omitted**, not fabricated, when its required optional input is absent —
  `condition_evaluator`'s missing-metric handling then correctly treats the rule as
  not-triggered rather than trusting a made-up zero.

## Files Changed

| File | Lines | What Changed |
|------|-------|-------------|
| `vinu_live/trade_plan/live_metrics.py` | — | Created |

## Verification

- [x] Tests pass (`tests/test_live_metrics.py`, 13 tests)
- [x] Type checks pass
- [x] Manual verification done
- [x] No runtime LLM call introduced outside `vinu-research`
