"""Tests for query-time indicators (TASK-S01)."""

from vinu_tools.compute.indicators.rsi.rsi import compute as _rsi_compute
from vinu_tools.compute.indicators.sma.sma import compute as _sma_compute

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


class TestDelegatesToVinuTools:
    """item #21 pattern #2: this module used to hand-roll SMA/RSI/MACD/
    volatility/ADX independently of vinu-tools' shared library -- these
    confirm it now genuinely delegates (same numbers vinu-tools itself
    would produce), not just a parallel implementation that happens to
    agree by luck."""

    def test_sma_matches_vinu_tools_exactly(self):
        rows = _sample_rows(30)
        out = apply_indicators(rows, ["sma_5"])
        tool_rows = [{"close": r["close"]} for r in rows]
        expected = _sma_compute(tool_rows, name="sma_5")["sma_5"]
        assert [r.get("sma_5") for r in out] == expected

    def test_rsi_matches_vinu_tools_exactly(self):
        rows = _sample_rows(30)
        out = apply_indicators(rows, ["rsi_14"])
        tool_rows = [{"close": r["close"]} for r in rows]
        expected = _rsi_compute(tool_rows, name="rsi_14")["rsi_14"]
        assert [r.get("rsi_14") for r in out] == expected

    def test_adx_with_missing_high_low_falls_back_to_close(self):
        """Preserves the pre-existing defensive behavior: a row missing
        high/low (only close present) must not crash vinu-tools' adx,
        which requires those keys."""
        rows = [{"close": 100.0 + i, "bar_ts": i} for i in range(40)]
        out = apply_indicators(rows, ["adx_14"])
        assert out[-1]["adx_14"] is not None

    def test_unsupported_name_is_silently_skipped(self):
        rows = _sample_rows(5)
        out = apply_indicators(rows, ["not_a_real_indicator"])
        assert "not_a_real_indicator" not in out[0]
