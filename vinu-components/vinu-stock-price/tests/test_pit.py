"""PIT test (18 step1): as-of join never sees the future.

Writes 10 minute bars, fetches with to_ts at bar 5, asserts only bars
<= to_ts return and SMA values match the sliced history (no future leak
into indicators through the query path: filter first, then aggregate,
then indicators).
"""
from pathlib import Path

from vinu_stock.query.engine import fetch_candles
from vinu_stock.storage import parquet
from vinu_stock.storage.models import BarRecord
from vinu_stock.storage.paths import archive_year_path


def _barsts(symbol: str, start: int, n: int) -> list[BarRecord]:
    return [
        BarRecord(
            symbol=symbol, provider="yahoo", bar_ts=start + i * 60,
            open=100.0 + i, high=101.0 + i, low=99.0 + i,
            close=100.0 + i, volume=1000.0,
        )
        for i in range(n)
    ]


def test_asof_excludes_future_bars(tmp_path: Path):
    bars = _barsts("PIT", 1_700_000_000, 10)
    out = archive_year_path(tmp_path, "PIT", 2023)
    parquet.write_bars(out, parquet.bars_to_table(bars), merge=False)
    cutoff = 1_700_000_000 + 4 * 60
    rows = fetch_candles(tmp_path, "PIT", interval="1m", to_ts=cutoff)
    assert len(rows) == 5
    assert all(r["bar_ts"] <= cutoff for r in rows)
    assert rows[-1]["close"] == 104.0


def test_indicators_match_sliced_history(tmp_path: Path):
    bars = _barsts("PIT2", 1_700_000_000, 10)
    out = archive_year_path(tmp_path, "PIT2", 2023)
    parquet.write_bars(out, parquet.bars_to_table(bars), merge=False)
    cutoff = 1_700_000_000 + 4 * 60
    a = fetch_candles(tmp_path, "PIT2", interval="1m", to_ts=cutoff, indicators=["SMA_3"])
    b = fetch_candles(tmp_path, "PIT2", interval="1m", indicators=["SMA_3"])
    # Same prefix values: early indicator output unaffected by later bars.
    assert [r["bar_ts"] for r in a] == [r["bar_ts"] for r in b[:5]]
    assert [r.get("SMA_3") for r in a] == [r.get("SMA_3") for r in b[:5]]
