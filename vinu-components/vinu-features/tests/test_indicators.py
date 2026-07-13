"""Tests for indicator computation."""

from vinu_features.compute.registry import apply_indicators, warmup_bars_for_features


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
