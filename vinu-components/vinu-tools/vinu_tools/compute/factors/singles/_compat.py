"""Backward-compat re-export: DataFrame-aware operators moved to operators.py.

Factor files import `from .._compat import *` — this now re-exports from
vinu_tools.compute.operators so all 461 existing files work unchanged.
"""

from vinu_tools.compute.operators import (  # noqa: F401, F403
    rank_df as rank,
    zscore_df as zscore,
    scale_df as scale,
    ts_rank_df as ts_rank,
    ts_corr_df as ts_corr,
    ts_cov_df as ts_cov,
    ts_mean_df as ts_mean,
    ts_std_df as ts_std,
    ts_max_df as ts_max,
    ts_min_df as ts_min,
    ts_argmax_df as ts_argmax,
    ts_argmin_df as ts_argmin,
    ts_sum_df as ts_sum,
    decay_linear_df as decay_linear,
    safe_div_df as safe_div,
    delta_df as delta,
    vwap_df as vwap,
    signed_power,
    cs_rank,
)


__all__ = [
    "rank", "zscore", "scale", "ts_rank", "ts_corr", "ts_cov",
    "ts_mean", "ts_std", "ts_max", "ts_min", "ts_argmax", "ts_argmin",
    "delta", "decay_linear", "signed_power", "safe_div", "vwap", "ts_sum",
    "cs_rank",
]
