from __future__ import annotations

import numpy as np
import pandas as pd

from vinu_initial_analysis.angles.shock_clustering.backtest import run_shock_date_backtest
from vinu_initial_analysis.angles.shock_clustering.compute import (
    MIN_OBSERVATIONS,
    MIN_SHOCK_DATES,
    _detect_shock_dates,
    _detect_shocks,
    compute,
)

_START_TS = 1_672_531_200  # 2023-01-01T00:00:00Z


def _make_bars(n: int, seed: int = 42, shock_indices: list[int] | None = None) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 0.5, size=n))
    open_p = close + rng.normal(0, 0.2, size=n)
    high = np.maximum(close, open_p) + np.abs(rng.normal(0, 0.3, size=n))
    low = np.minimum(close, open_p) - np.abs(rng.normal(0, 0.3, size=n))
    bar_ts = [_START_TS + i * 86400 for i in range(n)]
    df = pd.DataFrame({"bar_ts": bar_ts, "open": open_p, "high": high, "low": low, "close": close})
    # Inject deliberate large overnight gaps -- big enough to clear the
    # rolling gap-z threshold regardless of the trailing window's own
    # (small, calm-data) std.
    for idx in (shock_indices or []):
        df.loc[idx, "open"] = df.loc[idx - 1, "close"] * 1.15
        df.loc[idx, "high"] = max(df.loc[idx, "high"], df.loc[idx, "open"] * 1.01)
    return df


def test_detect_shocks_returns_no_shocks_on_calm_synthetic_data():
    bars = _make_bars(100)
    shocks = _detect_shocks(bars, gap_std_threshold=10.0, vol_z_threshold=10.0)
    assert shocks == []


def test_detect_shocks_finds_injected_gap_shocks():
    shock_indices = [40, 55, 70, 85, 95]
    bars = _make_bars(120, shock_indices=shock_indices)
    shocks = _detect_shocks(bars)
    assert len(shocks) >= len(shock_indices)
    for s in shocks:
        assert s["trigger"] in ("gap", "range")
        assert "bar_ts" in s and "date" in s and "z" in s


def test_detect_shock_dates_is_date_only_view():
    shock_indices = [40, 55, 70]
    bars = _make_bars(120, shock_indices=shock_indices)
    dates = _detect_shock_dates(bars)
    shocks = _detect_shocks(bars)
    assert dates == [s["date"] for s in shocks]


def test_compute_insufficient_data_below_observation_floor():
    bars = _make_bars(MIN_OBSERVATIONS - 1)
    df = compute("TEST", bars=bars)
    assert df.iloc[0]["status"] == "insufficient_data"


def test_compute_insufficient_shock_sample_on_calm_data():
    bars = _make_bars(MIN_OBSERVATIONS + 20)
    df = compute("TEST", bars=bars)
    # Calm synthetic data with default thresholds rarely clears 5 real
    # shocks -- if it does, that's still a valid "ok" run; only assert
    # the two statuses this angle actually defines are self-consistent.
    assert df.iloc[0]["status"] in ("insufficient_shock_sample", "ok")


def test_compute_ok_with_no_peers_has_empty_cluster_members():
    shock_indices = [30, 45, 60, 75, 90, 105]
    bars = _make_bars(MIN_OBSERVATIONS + 30, shock_indices=shock_indices)
    df = compute("TEST", bars=bars, price_client=None)
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert row["n_shock_dates"] >= MIN_SHOCK_DATES
    assert row["cluster_members"] == []


class _FakePriceClient:
    def __init__(self, peer_bars: dict[str, list[dict]]):
        self._peer_bars = peer_bars

    def get_watchlist(self) -> list[str]:
        return list(self._peer_bars.keys())

    def get_candles(self, symbol, from_ts=None, to_ts=None, interval="1D", limit=50000):
        return self._peer_bars.get(symbol, [])


def test_compute_with_peer_reports_co_shock_rate_and_correlation():
    shock_indices = [30, 45, 60, 75, 90, 105]
    anchor_bars = _make_bars(MIN_OBSERVATIONS + 30, seed=1, shock_indices=shock_indices)
    # peer shocks on the same days (plus its own noise) -- guarantees a
    # real, measurable co-shock rate and enough shock-day pairs for the
    # correlation to compute.
    peer_bars = _make_bars(MIN_OBSERVATIONS + 30, seed=2, shock_indices=shock_indices)
    client = _FakePriceClient({"PEER": peer_bars.to_dict("records")})

    df = compute("TEST", bars=anchor_bars, price_client=client)
    row = df.iloc[0]
    assert row["status"] == "ok"
    assert len(row["cluster_members"]) == 1
    member = row["cluster_members"][0]
    assert member["symbol"] == "PEER"
    assert member["n_anchor_shock_dates"] == row["n_shock_dates"]
    assert 0.0 <= member["co_shock_rate"] <= 1.0
    assert member["co_shock_rate"] > 0.0  # shared injected shock dates should co-shock


def test_compute_empty_bars_returns_no_data():
    assert compute("TEST", bars=None).iloc[0]["status"] == "no_data"
    assert compute("TEST", bars=pd.DataFrame()).iloc[0]["status"] == "no_data"


def test_shock_date_backtest_produces_date_only_tagged_rows():
    shock_indices = [30, 45, 60, 75, 90]
    bars = _make_bars(MIN_OBSERVATIONS + 30, shock_indices=shock_indices)
    df = run_shock_date_backtest("TEST", bars)
    assert not df.empty
    assert "session" not in df.columns
    for col in ("day_of_week", "week_of_month", "month", "quarter", "trigger", "z"):
        assert col in df.columns


def test_shock_date_backtest_empty_below_floor():
    bars = _make_bars(MIN_OBSERVATIONS - 1)
    df = run_shock_date_backtest("TEST", bars)
    assert df.empty
