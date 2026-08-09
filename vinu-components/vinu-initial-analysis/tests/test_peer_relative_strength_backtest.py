from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.peer_relative_strength.backtest import (
    run_forward_return_validation,
    run_relative_strength_backtest,
)
from vinu_initial_analysis.angles.peer_relative_strength.compute import ROLLING_CORR_WINDOW

_START_TS = 1_672_531_200  # 2023-01-01T00:00:00Z


def _make_bars(n_days: int, seed: int) -> tuple[pd.DataFrame, list[dict]]:
    rng = np.random.default_rng(seed)
    price = 100.0
    bar_dicts = []
    for i in range(n_days):
        ts = _START_TS + i * 86400
        price = max(price + rng.normal(0, 1.0), 1.0)
        bar_dicts.append({"bar_ts": ts, "close": price})
    return pd.DataFrame(bar_dicts), bar_dicts


class _FakePriceClient:
    def __init__(self, peer_bars: dict[str, list[dict]]):
        self._peer_bars = peer_bars

    def get_watchlist(self) -> list[str]:
        return list(self._peer_bars.keys())

    def get_candles(self, symbol: str, from_ts=None, to_ts=None, interval="1D", limit=50000) -> list[dict]:
        return self._peer_bars.get(symbol, [])


def _make_client_and_bars(n_days: int = 400):
    own_df, _ = _make_bars(n_days, seed=1)
    _, msft = _make_bars(n_days, seed=2)
    _, googl = _make_bars(n_days, seed=3)
    client = _FakePriceClient({"MSFT": msft, "GOOGL": googl})
    return own_df, client


def test_relative_strength_backtest_produces_date_only_tags():
    bars, client = _make_client_and_bars()
    df = run_relative_strength_backtest("AAPL", bars, price_client=client)
    assert not df.empty
    assert "session" not in df.columns
    assert "subsession" not in df.columns
    for col in ("day_of_week", "week_of_month", "month", "quarter"):
        assert col in df.columns
    assert set(df["peer_symbol"].unique()) == {"MSFT", "GOOGL"}


def test_relative_strength_backtest_insufficient_data_returns_status_row():
    bars, client = _make_client_and_bars(n_days=ROLLING_CORR_WINDOW)
    df = run_relative_strength_backtest("AAPL", bars, price_client=client)
    assert df.iloc[0]["status"] == "insufficient_data"


def test_forward_return_validation_produces_ci_bounded_correlations():
    bars, client = _make_client_and_bars()
    df = run_forward_return_validation("AAPL", bars, price_client=client)
    assert not df.empty
    assert set(df["peer_symbol"].unique()) <= {"MSFT", "GOOGL"}
    for _, row in df.iterrows():
        assert row["quarter_key"]
        for n in (5, 10, 20):
            col = f"forward_{n}d_corr"
            if col in row and pd.notna(row[col]):
                assert -1.0 <= row[col] <= 1.0
                assert row[f"forward_{n}d_ci_lower"] <= row[f"forward_{n}d_ci_upper"]


def test_forward_return_validation_empty_on_no_peers():
    bars, _ = _make_bars(n_days=400, seed=1)
    df = run_forward_return_validation("AAPL", bars, price_client=None)
    assert df.empty
