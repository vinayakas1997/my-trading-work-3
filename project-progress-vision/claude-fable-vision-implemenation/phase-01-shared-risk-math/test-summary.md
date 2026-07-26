# Phase 1 — Test Summary

## Tests Run

| Test File | Test Name | Result |
|-----------|-----------|--------|
| `tests/test_risk_volatility.py` | test_annualization_factor | PASS |
| `tests/test_risk_volatility.py` | test_realized_volatility_constant_returns | PASS |
| `tests/test_risk_volatility.py` | test_realized_volatility_zero_returns | PASS |
| `tests/test_risk_volatility.py` | test_realized_volatility_known_values | PASS |
| `tests/test_risk_volatility.py` | test_ewma_volatility_basic | PASS |
| `tests/test_risk_volatility.py` | test_ewma_volatility_decay | PASS |
| `tests/test_risk_volatility.py` | test_garch_volatility_fit | PASS |
| `tests/test_risk_volatility.py` | test_garch_volatility_fixed_params | PASS |
| `tests/test_risk_volatility.py` | test_garch_volatility_short_input | PASS |
| `tests/test_risk_volatility.py` | test_egarch_volatility_basic | PASS |
| `tests/test_risk_volatility.py` | test_egarch_volatility_asymmetry | PASS |
| `tests/test_risk_var.py` | test_historical_var_basic | PASS |
| `tests/test_risk_var.py` | test_historical_var_confidence_levels | PASS |
| `tests/test_risk_var.py` | test_historical_var_short_input | PASS |
| `tests/test_risk_var.py` | test_historical_cvar | PASS |
| `tests/test_risk_var.py` | test_parametric_var_basic | PASS |
| `tests/test_risk_var.py` | test_parametric_var_vs_historical | PASS |
| `tests/test_risk_var.py` | test_parametric_cvar | PASS |
| `tests/test_risk_expected_move.py` | test_expected_move_from_vol | PASS |
| `tests/test_risk_expected_move.py` | test_expected_move_95pct | PASS |
| `tests/test_risk_expected_move.py` | test_expected_range | PASS |
| `tests/test_risk_expected_move.py` | test_straddle_approximation | PASS |
| `tests/test_risk_expected_move.py` | test_straddle_approximation_zero_vol | PASS |
| `tests/test_risk_expected_move.py` | test_expected_move_over_period | PASS |
| `tests/test_risk_position_sizing.py` | test_kelly_fair_coin | PASS |
| `tests/test_risk_position_sizing.py` | test_kelly_with_edge | PASS |
| `tests/test_risk_position_sizing.py` | test_kelly_fraction_of_kelly | PASS |
| `tests/test_risk_position_sizing.py` | test_risk_budget_stop_loss | PASS |
| `tests/test_risk_position_sizing.py` | test_risk_budget_volatility | PASS |
| `tests/test_risk_position_sizing.py` | test_volatility_parity_weights | PASS |
| `tests/test_risk_position_sizing.py` | test_volatility_parity_equal | PASS |
| `tests/test_risk_position_sizing.py` | test_max_position_size | PASS |
| `tests/test_risk_position_sizing.py` | test_max_position_size_zero_vol | PASS |
| `tests/test_risk_greeks.py` | test_call_delta_atm | PASS |
| `tests/test_risk_greeks.py` | test_put_delta_atm | PASS |
| `tests/test_risk_greeks.py` | test_call_delta_itm | PASS |
| `tests/test_risk_greeks.py` | test_call_delta_otm | PASS |
| `tests/test_risk_greeks.py` | test_gamma_positive | PASS |
| `tests/test_risk_greeks.py` | test_vega_positive | PASS |
| `tests/test_risk_greeks.py` | test_theta_call | PASS |
| `tests/test_risk_greeks.py` | test_rho_call_positive | PASS |
| `tests/test_risk_covariance.py` | test_dynamic_covariance_basic | PASS |
| `tests/test_risk_covariance.py` | test_dynamic_covariance_single_asset | PASS |
| `tests/test_risk_covariance.py` | test_dynamic_covariance_symmetric | PASS |
| `tests/test_risk_covariance.py` | test_dynamic_covariance_shrinkage | PASS |
| `tests/test_risk_covariance.py` | test_dynamic_covariance_exponential | PASS |
| `tests/test_risk_covariance.py` | test_portfolio_variance | PASS |
| `tests/test_risk_covariance.py` | test_portfolio_variance_equal_weight | PASS |
| `tests/test_risk_covariance.py` | test_correlation_from_covariance | PASS |

## Coverage Notes

- All risk modules have known-input/known-output tests
- GARCH fit uses synthetic clustered-vol series to verify tracking
- Greeks tested against reference Black-Scholes values
- Dynamic covariance tested with synthetic basket correlation regime shifts
- Property test confirms position size never exceeds risk budget

## Verdict

49 tests pass. No regressions detected.
