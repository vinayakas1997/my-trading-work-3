"""Alpha bench — IC analysis, factor classification, backtesting, decay.

Entry points:
    bench_factor(id, panel)    → single factor IC + ALIVE/DEAD
    bench_factors(ids, panel)  → multiple factors, ranked by |IC|
    bench_zoo(zoo, panel)      → entire group (gtja191, alpha101, etc.)
    backtest_factor(...)       → long/short portfolio simulation
    compute_ic(...)            → Spearman IC time series
    compute_ic_decay(...)      → IC decay curve
    estimate_half_life(...)    → IC half-life
"""

from vinu_tools.compute.bench.runner import bench_factor, bench_factors, bench_zoo
from vinu_tools.compute.bench.backtest import FactorBacktestResult, backtest_factor, compare_factors
from vinu_tools.compute.bench.decay import compute_ic, compute_ic_decay, compute_turnover, estimate_half_life

__all__ = [
    "bench_factor", "bench_factors", "bench_zoo",
    "backtest_factor", "compare_factors", "FactorBacktestResult",
    "compute_ic", "compute_ic_decay", "compute_turnover", "estimate_half_life",
]
