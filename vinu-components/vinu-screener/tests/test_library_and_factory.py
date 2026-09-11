from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from vinu_screener.features.factory import IndicatorFactory
from vinu_screener.features.library import (
    FeatureLibrary,
    IndicatorSpec,
    UnknownIndicatorError,
)


def _ohlcv(n: int = 60, seed: int = 0, close_start: float = 100.0) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    close = close_start + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame({
        "open": close, "high": close + 1, "low": close - 1, "close": close,
        "volume": rng.integers(1000, 5000, n).astype(float),
    })


class TestFeatureLibrary:
    def test_close_passthrough(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        out = lib.compute("AAPL", df, "close")
        assert (out == df["close"]).all()

    def test_dollar_volume_is_close_times_volume(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        out = lib.compute("AAPL", df, "dollar_volume")
        assert out.iloc[-1] == pytest.approx(df["close"].iloc[-1] * df["volume"].iloc[-1])

    def test_unknown_indicator_raises(self) -> None:
        lib = FeatureLibrary()
        with pytest.raises(UnknownIndicatorError):
            lib.compute("AAPL", _ohlcv(), "not_a_real_indicator")

    def test_missing_column_raises_keyerror(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv().drop(columns=["volume"])
        with pytest.raises(KeyError):
            lib.compute("AAPL", df, "dollar_volume")

    def test_cache_returns_the_same_object_within_a_cycle(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        a = lib.compute("AAPL", df, "sma", {"period": 20})
        b = lib.compute("AAPL", df, "sma", {"period": 20})
        assert a is b  # cached, not recomputed

    def test_different_params_are_not_confused_by_the_cache(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        a = lib.compute("AAPL", df, "sma", {"period": 10})
        b = lib.compute("AAPL", df, "sma", {"period": 20})
        assert a is not b
        assert a.iloc[-1] != b.iloc[-1]

    def test_clear_cache_forces_recompute(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        a = lib.compute("AAPL", df, "sma", {"period": 20})
        lib.clear_cache()
        b = lib.compute("AAPL", df, "sma", {"period": 20})
        assert a is not b  # new object post-clear, even though the values match

    def test_field_selects_a_macd_column(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        result = lib.compute("AAPL", df, "macd")
        sig = lib.field(result, "signal")
        assert sig.equals(result["signal"])  # NaN-safe equality

    def test_field_on_a_series_ignores_field_name(self) -> None:
        lib = FeatureLibrary()
        df = _ohlcv()
        result = lib.compute("AAPL", df, "close")
        assert lib.field(result, "value") is result

    def test_field_rejects_an_unknown_column_on_a_dataframe_result(self) -> None:
        lib = FeatureLibrary()
        result = lib.compute("AAPL", _ohlcv(), "macd")
        with pytest.raises(KeyError):
            lib.field(result, "nonexistent")

    def test_custom_indicator_can_be_registered(self) -> None:
        lib = FeatureLibrary()
        lib.register(IndicatorSpec("double_close", ("close",), lambda c: c * 2))
        df = _ohlcv()
        out = lib.compute("AAPL", df, "double_close")
        assert out.iloc[-1] == pytest.approx(df["close"].iloc[-1] * 2)


class TestIndicatorFactoryBroadcast:
    def test_broadcasts_across_every_symbol(self) -> None:
        factory = IndicatorFactory()
        universe = {"AAPL": _ohlcv(seed=1), "MSFT": _ohlcv(seed=2, close_start=300.0)}
        out = factory.broadcast("sma", universe, {"period": 10})
        assert set(out) == {"AAPL", "MSFT"}

    def test_shares_one_cache_across_the_whole_universe(self) -> None:
        # same symbol referenced twice in two calls -> same cached object
        factory = IndicatorFactory()
        df = _ohlcv()
        universe = {"AAPL": df}
        a = factory.broadcast("sma", universe, {"period": 10})["AAPL"]
        b = factory.broadcast("sma", universe, {"period": 10})["AAPL"]
        assert a is b

    def test_symbol_missing_required_column_is_skipped_not_raised(self) -> None:
        factory = IndicatorFactory()
        good = _ohlcv()
        bad = _ohlcv().drop(columns=["volume"])
        universe = {"AAPL": good, "BROKEN": bad}
        out = factory.broadcast("dollar_volume", universe)
        assert "AAPL" in out
        assert "BROKEN" not in out

    def test_latest_returns_one_float_per_symbol(self) -> None:
        factory = IndicatorFactory()
        universe = {"AAPL": _ohlcv(seed=3), "MSFT": _ohlcv(seed=4, close_start=250.0)}
        out = factory.latest("close", universe)
        assert isinstance(out["AAPL"], float)
        assert out["AAPL"] == pytest.approx(universe["AAPL"]["close"].iloc[-1])

    def test_latest_drops_nan_results(self) -> None:
        factory = IndicatorFactory()
        # sma(50) on a 10-row frame is all-NaN
        universe = {"TOO_SHORT": _ohlcv(n=10)}
        out = factory.latest("sma", universe, {"period": 50})
        assert "TOO_SHORT" not in out

    def test_latest_honours_offset(self) -> None:
        factory = IndicatorFactory()
        df = _ohlcv(n=30)
        universe = {"AAPL": df}
        current = factory.latest("close", universe)["AAPL"]
        one_ago = factory.latest("close", universe, offset=1)["AAPL"]
        assert current == pytest.approx(df["close"].iloc[-1])
        assert one_ago == pytest.approx(df["close"].iloc[-2])

    def test_latest_selects_a_multi_output_field(self) -> None:
        factory = IndicatorFactory()
        universe = {"AAPL": _ohlcv(n=60)}
        out = factory.latest("macd", universe, field="signal")
        assert "AAPL" in out
