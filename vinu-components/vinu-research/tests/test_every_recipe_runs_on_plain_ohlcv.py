"""Every built-in recipe must run on plain OHLCV with the float params a sweep
grid sends. The RSI recipe once read a precomputed column named from the
period ('rsi_14.0' with a float period) and crashed for every symbol, which
the simulator reported as 'No weight data generated'."""
from __future__ import annotations

import sys
import types

import numpy as np
import pandas as pd
import pytest

from vinu_research.generator import (
    DEFAULT_PARAMS,
    TEMPLATE_METADATA,
    generate_strategy,
    list_recipes,
)


@pytest.fixture(autouse=True)
def _stub_base_strategy(monkeypatch):
    """Generated code imports BaseStrategy from the simulator; a stub is enough
    to exercise generate_weights without that package installed."""
    mod = types.ModuleType("vinu_simulator.engine.strategies")
    mod.BaseStrategy = type("BaseStrategy", (), {})
    for name in ("vinu_simulator", "vinu_simulator.engine"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "vinu_simulator.engine.strategies", mod)


def _ohlcv(n: int = 400) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.02, n)))
    idx = pd.date_range("2023-01-02", periods=n, freq="B")
    return pd.DataFrame(
        {"open": close, "high": close * 1.01, "low": close * 0.99,
         "close": close, "volume": rng.integers(1_000, 5_000, n).astype(float)},
        index=idx,
    )


def _weights(recipe: str, params: dict[str, float]) -> pd.Series:
    scope: dict = {}
    exec(generate_strategy(recipe=recipe, params=params), scope)  # noqa: S102
    return scope["UserStrategy"]().generate_weights(_ohlcv())


@pytest.mark.parametrize("recipe", list_recipes())
def test_recipe_runs_with_float_default_params_and_no_indicator_columns(recipe):
    w = _weights(recipe, {k: float(v) for k, v in DEFAULT_PARAMS.items() if k != "allocation"})
    assert isinstance(w, pd.Series) and len(w) == 400


@pytest.mark.parametrize("period", [7.0, 14.0, 21.0])
def test_rsi_recipe_trades_at_any_period(period):
    """A grid varies the period; only rsi_14 exists as a stored column, so the
    recipe has to compute RSI itself. It must also actually trade."""
    w = _weights("rsi", {"rsi_period": period, "oversold": 40.0, "overbought": 60.0})
    assert (w != 0).any()
