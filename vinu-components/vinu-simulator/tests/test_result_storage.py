"""Tests for ResultStorage -- item #13 finding #6 (no dedicated test
file existed for this module at all) and finding #2 (a regression guard
for the fix itself: `meta.json` used to duplicate
strategy_name/run_id/timestamp already in MetaStorage's own SQL row, with
`load_meta()` as its only reader -- confirmed nothing calls `load_meta()`
anywhere in the real codebase, so both the write and the dead reader were
removed rather than redirected)."""

from __future__ import annotations

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from vinu_simulator.models.simulation import SimulationConfig, SimulationResult, TradeRecord
from vinu_simulator.storage.results import ResultStorage


def _result(run_id: str = "run-001") -> SimulationResult:
    dates = pd.date_range("2024-01-02", periods=5, freq="D")
    portfolio_values = pd.Series([100_000.0, 101_000.0, 100_500.0, 102_000.0, 103_000.0], index=dates)
    daily_returns = portfolio_values.pct_change().fillna(0.0)
    weights_history = pd.DataFrame({"AAPL": [0.5] * 5, "MSFT": [0.5] * 5}, index=dates)
    trades = [
        TradeRecord(
            date=dates[1], symbol="AAPL", side="buy", shares=10.0, price=150.0,
            cost=1500.0, weight_before=0.4, weight_after=0.5,
        ),
    ]
    config = SimulationConfig(strategy_name="TestStrategy", start_date="2024-01-02", end_date="2024-01-06")
    return SimulationResult(
        strategy_name="TestStrategy", run_id=run_id, timestamp=datetime.now(timezone.utc),
        config=config, portfolio_values=portfolio_values, daily_returns=daily_returns,
        weights_history=weights_history, trades=trades, metrics={"sharpe_ratio": 1.1},
    )


def _storage() -> tuple[ResultStorage, Path]:
    tmp = Path(tempfile.mkdtemp())
    return ResultStorage(tmp), tmp


class TestSaveAndLoadRoundTrip:
    def test_equity_round_trips(self):
        storage, _ = _storage()
        result = _result()
        storage.save(result)
        loaded = storage.load_equity(result.run_id)
        assert len(loaded) == 5
        assert "portfolio_value" in loaded.columns
        assert "daily_return" in loaded.columns

    def test_weights_round_trip(self):
        storage, _ = _storage()
        result = _result()
        storage.save(result)
        loaded = storage.load_weights(result.run_id)
        assert len(loaded) == 5
        assert "AAPL" in loaded.columns
        assert "MSFT" in loaded.columns

    def test_trades_round_trip(self):
        storage, _ = _storage()
        result = _result()
        storage.save(result)
        loaded = storage.load_trades(result.run_id)
        assert len(loaded) == 1
        assert loaded[0].symbol == "AAPL"
        assert loaded[0].shares == 10.0
        assert loaded[0].volume_capped is False

    def test_no_trades_returns_empty_list_not_a_missing_file_error(self):
        storage, _ = _storage()
        result = _result()
        result.trades = []
        storage.save(result)
        assert storage.load_trades(result.run_id) == []

    def test_load_for_unknown_run_id_returns_empty_not_raises(self):
        storage, _ = _storage()
        assert storage.load_equity("nonexistent").empty
        assert storage.load_weights("nonexistent").empty
        assert storage.load_trades("nonexistent") == []


class TestNoRedundantMetaJson:
    """item #13 finding #2: meta.json duplicated fields already in
    MetaStorage's own SQL row (strategy_name/run_id/timestamp), and
    nothing in the real codebase ever read it back (`load_meta()` had
    zero callers). Both removed rather than wired to a real reader that
    doesn't exist."""

    def test_save_does_not_write_a_meta_json_file(self):
        storage, tmp = _storage()
        result = _result()
        storage.save(result)
        rdir = tmp / "simulations" / result.run_id[:2] / result.run_id
        assert not (rdir / "meta.json").exists()
        # the real artifacts are still written
        assert (rdir / "equity.parquet").exists()
        assert (rdir / "weights.parquet").exists()

    def test_load_meta_is_no_longer_a_public_method(self):
        assert not hasattr(ResultStorage, "load_meta")


class TestDelete:
    def test_delete_removes_the_run_directory(self):
        storage, _ = _storage()
        result = _result()
        storage.save(result)
        assert storage.delete(result.run_id) is True
        assert storage.load_equity(result.run_id).empty

    def test_delete_nonexistent_run_returns_false(self):
        storage, _ = _storage()
        assert storage.delete("nonexistent") is False
