"""Tests for query-time indicators (TASK-S01)."""

from vinu_stock.query.indicators import apply_indicators, parse_indicator_names


def _sample_rows(n: int = 30) -> list[dict]:
    rows = []
    price = 100.0
    for i in range(n):
        price += 0.5
        rows.append(
            {
                "symbol": "TEST",
                "provider": "yahoo",
                "bar_ts": 1_700_000_000 + i * 60,
                "open": price - 0.2,
                "high": price + 0.3,
                "low": price - 0.4,
                "close": price,
                "volume": 1000.0,
            }
        )
    return rows


def test_parse_indicator_names():
    assert parse_indicator_names("rsi_14,sma_20") == ["rsi_14", "sma_20"]


def test_apply_sma_and_rsi():
    rows = _sample_rows(30)
    out = apply_indicators(rows, ["sma_5", "rsi_14"])
    assert out[-1]["sma_5"] is not None
    assert out[-1]["rsi_14"] is not None


def test_apply_adjusted_prices():
    from vinu_stock.query.indicators import apply_adjusted_prices

    rows = [{"open": 100.0, "high": 110.0, "low": 90.0, "close": 100.0, "adj_factor": 0.5}]
    out = apply_adjusted_prices(rows)
    assert out[0]["close"] == 50.0
