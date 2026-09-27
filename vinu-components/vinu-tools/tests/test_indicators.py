"""Tests for indicator computation."""

import pytest

from vinu_tools.compute.indicators._shared.rolling import wilder_smooth
from vinu_tools.compute.registry import apply_indicators, warmup_bars_for_features


def _candles(n: int, start: float = 100.0) -> list[dict]:
    rows = []
    for i in range(n):
        price = start + i * 0.5
        rows.append(
            {
                "ts": 1_700_000_000 + i * 86400,
                "symbol": "AAPL",
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 1000,
            }
        )
    return rows


def test_sma_100_computes():
    rows = _candles(120)
    out = apply_indicators(rows, ["sma_100"])
    assert out[98]["sma_100"] is None
    assert out[99]["sma_100"] is not None


def test_warmup_bars():
    assert warmup_bars_for_features(["sma_100", "rsi_14"]) >= 100


def test_session_computes():
    # 1700000000 is 2023-11-14 22:13:20 UTC
    rows = _candles(10)
    out = apply_indicators(rows, ["session"])
    assert "session" in out[0]
    assert out[0]["session"] in ("asia", "london", "ny_regular", "london_ny_overlap", "off_hours")


def test_ichimoku_computes_all_four_components_after_warmup():
    rows = _candles(70)
    out = apply_indicators(
        rows,
        ["ichimoku_tenkan", "ichimoku_kijun", "ichimoku_senkou_a", "ichimoku_senkou_b"],
    )
    # senkou_b needs 52 bars -- absent before that, present after.
    assert out[50]["ichimoku_senkou_b"] is None
    assert out[51]["ichimoku_senkou_b"] is not None
    assert out[69]["ichimoku_tenkan"] is not None
    assert out[69]["ichimoku_kijun"] is not None
    assert out[69]["ichimoku_senkou_a"] is not None


def test_parabolic_sar_computes_and_stays_bounded():
    rows = _candles(50)
    out = apply_indicators(rows, ["parabolic_sar"])
    assert out[0]["parabolic_sar"] is None
    assert out[1]["parabolic_sar"] is not None
    # Monotonic uptrend fixture -- SAR should trail below price throughout.
    for i in range(1, 50):
        assert out[i]["parabolic_sar"] < rows[i]["close"]


def test_mfi_computes_and_is_bounded_0_100():
    rows = _candles(30)
    out = apply_indicators(rows, ["mfi_14"])
    assert out[13]["mfi_14"] is None
    assert out[14]["mfi_14"] is not None
    for i in range(14, 30):
        assert 0.0 <= out[i]["mfi_14"] <= 100.0


def test_wilder_smooth_matches_hand_computed_known_values():
    """item #20 finding #3: ADX and ATR were both untested, which let the
    smoothing-method bugs (findings #1/#2) ship undetected -- a basic
    known-value test, per the audit's own suggestion. Hand-computed:
    seed = avg(1..5) = 3.0 at index 4, then Wilder's recursion
    avg = (avg*(period-1) + new)/period each step after."""
    result = wilder_smooth([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0], period=5)
    assert result[:4] == [None, None, None, None]
    assert result[4] == pytest.approx(3.0)
    assert result[5] == pytest.approx(3.6)
    assert result[6] == pytest.approx(4.28)
    assert result[7] == pytest.approx(5.024)
    assert result[9] == pytest.approx(6.65536)


def test_wilder_smooth_of_a_constant_series_stays_constant():
    result = wilder_smooth([5.0] * 20, period=5)
    assert result[3] is None
    for v in result[4:]:
        assert v == pytest.approx(5.0)


def test_wilder_smooth_too_short_returns_all_none():
    assert wilder_smooth([1.0, 2.0], period=5) == [None, None]


class TestATRUsesRealWilderSmoothing:
    """item #20 finding #2: atr.py used to be a plain SMA of true range,
    not Wilder-smoothed TR -- directly relevant to Decision 14's 2xATR(14)
    move-detection floor (../how-to-use-29th-angle/
    03-move-detection-threshold-options.md)."""

    def test_constant_true_range_gives_an_exact_known_atr(self):
        # high=101, low=99, close=100 every bar -> true range is exactly
        # 2.0 every bar (|101-99|=2 dominates |101-100| and |99-100|).
        # Wilder-smoothing a constant series stays exactly that constant.
        rows = [
            {"ts": 1_700_000_000 + i * 86400, "symbol": "AAPL",
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000}
            for i in range(20)
        ]
        out = apply_indicators(rows, ["atr_14"])
        assert out[12]["atr_14"] is None
        for i in range(13, 20):
            assert out[i]["atr_14"] == pytest.approx(2.0)

    def test_no_longer_a_plain_sma_of_true_range(self):
        """Regression guard for the actual bug: a widening true range must
        show Wilder's slower-to-react memory, not SMA's exact windowed
        average -- these differ for a non-constant series, which is
        exactly the case SMA silently got wrong before this fix."""
        rows = []
        price = 100.0
        for i in range(30):
            spread = 1.0 + i * 0.3  # widening true range each bar
            rows.append({
                "ts": 1_700_000_000 + i * 86400, "symbol": "AAPL",
                "open": price, "high": price + spread, "low": price - spread,
                "close": price, "volume": 1000,
            })
        out = apply_indicators(rows, ["atr_14"])
        atr_values = [out[i]["atr_14"] for i in range(13, 30)]
        assert all(v is not None for v in atr_values)

        from vinu_tools.compute.indicators._shared.rolling import sma, true_range
        highs = [r["high"] for r in rows]
        lows = [r["low"] for r in rows]
        closes = [r["close"] for r in rows]
        tr = true_range(highs, lows, closes)
        plain_sma_atr = sma(tr, 14)
        # The old (buggy) formula's own answer at the same indices --
        # confirms the fix actually changed the output, not just the
        # code path.
        assert out[20]["atr_14"] != pytest.approx(plain_sma_atr[20])


class TestADXUsesRealWilderSmoothing:
    """item #20 finding #1: adx.py used to smooth via standard EMA
    (alpha=2/(period+1)), not real Wilder smoothing (alpha=1/period)."""

    def test_flat_market_has_zero_adx_once_defined(self):
        rows = [
            {"ts": 1_700_000_000 + i * 86400, "symbol": "AAPL",
             "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1000}
            for i in range(40)
        ]
        out = apply_indicators(rows, ["adx_14"])
        assert out[27]["adx_14"] is None
        for i in range(28, 40):
            assert out[i]["adx_14"] == pytest.approx(0.0, abs=1e-6)

    def test_a_strong_steady_uptrend_pushes_adx_toward_100(self):
        rows = []
        price = 100.0
        for i in range(60):
            price += 1.0  # every bar makes a new high -- pure +DM, zero -DM
            rows.append({
                "ts": 1_700_000_000 + i * 86400, "symbol": "AAPL",
                "open": price - 0.4, "high": price + 0.5, "low": price - 0.5,
                "close": price, "volume": 1000,
            })
        out = apply_indicators(rows, ["adx_14"])
        assert out[27]["adx_14"] is None
        assert out[28]["adx_14"] is not None
        for i in range(28, 60):
            assert 0.0 <= out[i]["adx_14"] <= 100.0
        # Monotonically strengthening trend signal as the zero-seeded
        # warmup's influence decays out of the Wilder recursion.
        assert out[59]["adx_14"] > out[30]["adx_14"]
        assert out[59]["adx_14"] > 80.0


def test_accumulation_distribution_line_is_cumulative():
    # Close pinned near the HIGH each bar (not centered, unlike
    # `_candles`' symmetric high/low) -- gives a real positive
    # money-flow-multiplier every bar, so the running total actually
    # accumulates rather than staying trivially at 0.
    rows = []
    price = 100.0
    for i in range(20):
        price += 0.5
        rows.append({
            "ts": 1_700_000_000 + i * 86400, "symbol": "AAPL",
            "open": price - 0.8, "high": price + 0.1, "low": price - 1.0,
            "close": price, "volume": 1000,
        })
    out = apply_indicators(rows, ["accumulation_distribution_line"])
    assert out[0]["accumulation_distribution_line"] is not None
    prev = out[0]["accumulation_distribution_line"]
    for i in range(1, 20):
        cur = out[i]["accumulation_distribution_line"]
        assert cur > prev
        prev = cur

