"""Tests for indicator computation."""

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

