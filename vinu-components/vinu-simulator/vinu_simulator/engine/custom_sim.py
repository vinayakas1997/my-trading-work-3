from __future__ import annotations

import logging
from typing import Any

from vinu_lib.debug import sync_timer

import numpy as np
import pandas as pd

from vinu_simulator.engine.simulator import WeightSimulator
from vinu_simulator.engine.strategies import BaseStrategy
from vinu_simulator.models.simulation import SimulationConfig, SimulationInput, SimulationResult

LOG = logging.getLogger(__name__)


def simulate_custom(
    strategy_class: type[BaseStrategy],
    symbols: list[str],
    ohclv_data: dict[str, pd.DataFrame],
    sim_config: SimulationConfig,
    indicator_data: dict[str, pd.DataFrame] | None = None,
    strategy_kwargs: dict[str, Any] | None = None,
) -> SimulationResult:
    if strategy_kwargs is None:
        strategy_kwargs = {}
    try:
        strategy = strategy_class(**strategy_kwargs)
    except Exception as e:
        raise ValueError(f"Failed to instantiate {strategy_class.__name__}: {e}") from e

    per_ticker_weights: dict[str, pd.Series] = {}
    all_dates: set[pd.Timestamp] = set()

    for sym in symbols:
        df = ohclv_data.get(sym)
        if df is None or df.empty:
            per_ticker_weights[sym] = pd.Series(dtype=float)
            continue

        try:
            data = df[["open", "high", "low", "close", "volume"]].copy()
        except KeyError as e:
            LOG.warning("Symbol %s missing OHLCV columns: %s, using zeros", sym, e)
            per_ticker_weights[sym] = pd.Series(dtype=float)
            continue

        if indicator_data and sym in indicator_data:
            ind_df = indicator_data[sym]
            if not ind_df.empty:
                for col in ind_df.columns:
                    data[col] = ind_df[col]

        try:
            with sync_timer(f"weights.{sym}"):
                weights = strategy.generate_weights(data)
        except Exception as e:
            LOG.warning("generate_weights failed for %s: %s, using zeros", sym, e)
            per_ticker_weights[sym] = pd.Series(index=data.index, data=0.0)
            continue

        if not isinstance(weights, pd.Series):
            LOG.warning("generate_weights for %s returned %s, expected Series, using zeros",
                        sym, type(weights).__name__)
            per_ticker_weights[sym] = pd.Series(index=data.index, data=0.0)
            continue

        if weights.empty:
            per_ticker_weights[sym] = pd.Series(index=data.index, data=0.0)
        else:
            weights = weights.reindex(data.index).fillna(0.0)
            per_ticker_weights[sym] = weights
            all_dates.update(weights.index)

    if not all_dates:
        raise ValueError("No weight data generated — all symbols returned empty")

    sorted_dates = sorted(all_dates)
    weight_matrix = pd.DataFrame(
        {sym: per_ticker_weights.get(sym, pd.Series(dtype=float)).reindex(sorted_dates).fillna(0.0)
         for sym in symbols},
        index=sorted_dates,
    )
    weight_matrix = _normalize_weights(weight_matrix)

    prices_list = []
    for sym in symbols:
        close = ohclv_data[sym]["close"].reindex(sorted_dates)
        prices_list.append(close)
    price_matrix = pd.concat(prices_list, axis=1)
    price_matrix.columns = symbols
    # Forward-fill only. bfill() would leak a future price backward into any date
    # before a symbol's first available trade (or into a mid-series gap) — the
    # engine's WeightSimulator.run() already raises a clear ValueError below if any
    # NaN survives the forward-fill, which is the correct behavior for a real gap.
    price_matrix = price_matrix.ffill()

    volumes_list = []
    for sym in symbols:
        vol = ohclv_data[sym]["volume"].reindex(sorted_dates).fillna(0.0)
        volumes_list.append(vol)
    volume_matrix = pd.concat(volumes_list, axis=1)
    volume_matrix.columns = symbols

    inp = SimulationInput(
        strategy_name=strategy_class.__name__,
        weight_signals=weight_matrix,
        price_data=price_matrix,
        config=sim_config,
        volume_data=volume_matrix,
    )

    simulator = WeightSimulator(sim_config)
    result = simulator.run(inp)
    return result


def _normalize_weights(weights: pd.DataFrame) -> pd.DataFrame:
    abs_sums = weights.abs().sum(axis=1)
    divisor = abs_sums.where(abs_sums > 1.0, other=1.0)
    return weights.div(divisor, axis=0)
