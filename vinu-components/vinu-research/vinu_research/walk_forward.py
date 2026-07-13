from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from statistics import NormalDist

_STANDARD_NORMAL = NormalDist()
_EULER_GAMMA = 0.5772156649015329


@dataclass
class WalkForwardConfig:
    method: str = "expanding"
    train_pct: float = 0.6
    val_pct: float = 0.2
    test_pct: float = 0.2
    n_windows: int = 3
    min_train_days: int = 252
    step_size_days: int = 63
    gap_days: int = 5


@dataclass
class WalkForwardWindow:
    window_id: int
    train_start: str
    train_end: str
    test_start: str
    test_end: str


class WindowSplitter:
    def __init__(self, config: WalkForwardConfig):
        self.config = config

    def split(self, from_date: str, to_date: str) -> list[WalkForwardWindow]:
        from_dt = datetime.strptime(from_date, "%Y-%m-%d")
        to_dt = datetime.strptime(to_date, "%Y-%m-%d")
        total_days = (to_dt - from_dt).days

        if total_days < self.config.min_train_days * 1.5:
            return []

        train_size = int(total_days * self.config.train_pct)
        test_size = int(total_days * self.config.test_pct)
        step = max(self.config.step_size_days, test_size // 2)

        windows: list[WalkForwardWindow] = []
        for i in range(self.config.n_windows):
            if self.config.method == "expanding":
                train_end_offset = int(train_size * (i + 1) / self.config.n_windows)
                train_start_dt = from_dt
                train_end_dt = from_dt + timedelta(days=train_end_offset)
            else:
                train_start_dt = from_dt + timedelta(days=i * step)
                train_end_dt = train_start_dt + timedelta(days=train_size)

            if train_end_dt > to_dt:
                break

            test_start_dt = train_end_dt + timedelta(days=self.config.gap_days)
            test_end_dt = test_start_dt + timedelta(days=test_size)

            if test_end_dt > to_dt:
                test_end_dt = to_dt
            if test_start_dt >= test_end_dt:
                continue

            windows.append(
                WalkForwardWindow(
                    window_id=i + 1,
                    train_start=train_start_dt.strftime("%Y-%m-%d"),
                    train_end=train_end_dt.strftime("%Y-%m-%d"),
                    test_start=test_start_dt.strftime("%Y-%m-%d"),
                    test_end=test_end_dt.strftime("%Y-%m-%d"),
                )
            )

        return windows


def aggregate_metrics(
    is_metrics_list: list[dict[str, float]],
    oos_metrics_list: list[dict[str, float]],
) -> tuple[dict[str, float], dict[str, float]]:
    if not is_metrics_list or not oos_metrics_list:
        return {}, {}

    import numpy as np

    is_aggregated: dict[str, float] = {}
    oos_aggregated: dict[str, float] = {}

    for key in is_metrics_list[0]:
        values = [m.get(key, 0.0) for m in is_metrics_list]
        is_aggregated[key] = float(np.median(values))
        # Dispersion across windows — a median alone hides whether the strategy is
        # consistently OK or swings between great and terrible windows.
        is_aggregated[f"{key}_std"] = float(np.std(values)) if len(values) > 1 else 0.0

    for key in oos_metrics_list[0]:
        values = [m.get(key, 0.0) for m in oos_metrics_list]
        oos_aggregated[key] = float(np.median(values))
        oos_aggregated[f"{key}_std"] = float(np.std(values)) if len(values) > 1 else 0.0

    # Fraction of out-of-sample windows that lost money — a strategy can have a
    # decent median OOS Sharpe while still losing money in a third of windows.
    oos_returns = [m.get("total_return", 0.0) for m in oos_metrics_list]
    oos_aggregated["losing_window_fraction"] = float(
        sum(1 for r in oos_returns if r < 0) / len(oos_returns)
    )

    return is_aggregated, oos_aggregated


def deflated_sharpe_ratio(
    sharpe: float,
    n_trials: int,
    n_obs: int,
    skew: float = 0.0,
    excess_kurtosis: float = 0.0,
) -> float:
    """
    Bailey & Lopez de Prado (2014) Deflated Sharpe Ratio: the probability that the
    observed Sharpe ratio reflects genuine skill after accounting for having been
    selected as the best of `n_trials` independent backtests run against the same
    data (e.g. LLM candidates, or repeated refinement iterations).

    Despite the name this returns a probability in [0, 1], not a Sharpe ratio.
    ~0.5 means "indistinguishable from what pure luck would produce by trying this
    many strategies" — not "mediocre." Values need to clear roughly 0.95 to be
    treated as evidence of real skill under the standard multiple-testing correction.

    `excess_kurtosis` follows the pandas/numpy convention (0.0 for a normal
    distribution), matching `BacktestMetrics.kurtosis`.
    """
    if n_obs < 2 or n_trials < 1:
        return 0.5

    kurt = excess_kurtosis + 3.0  # convert to regular (non-excess) kurtosis
    variance_term = max(1 - skew * sharpe + ((kurt - 1) / 4) * sharpe**2, 1e-12)
    sr_std = math.sqrt(variance_term / max(n_obs - 1, 1))
    if sr_std <= 0:
        return 0.5

    if n_trials <= 1:
        expected_max_sharpe = 0.0
    else:
        z_a = _STANDARD_NORMAL.inv_cdf(1 - 1.0 / n_trials)
        z_b = _STANDARD_NORMAL.inv_cdf(1 - 1.0 / (n_trials * math.e))
        expected_max_sharpe = sr_std * ((1 - _EULER_GAMMA) * z_a + _EULER_GAMMA * z_b)

    z = (sharpe - expected_max_sharpe) / sr_std
    return float(_STANDARD_NORMAL.cdf(z))
