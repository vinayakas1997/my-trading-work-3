"""03_adjustments.py — Corporate action adjustments.

Uses adjustment="all" to smooth prices over stock splits and dividends.
Compare adjusted vs. unadjusted data to see the difference.
"""

from datetime import datetime, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config

cfg = load_config()
client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

symbol = "AAPL"

request_raw = StockBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame(1, TimeFrameUnit.Day),
    start=datetime(2020, 1, 1, tzinfo=timezone.utc),
    end=datetime(2025, 1, 1, tzinfo=timezone.utc),
    adjustment="raw",
)

request_adj = StockBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame(1, TimeFrameUnit.Day),
    start=datetime(2020, 1, 1, tzinfo=timezone.utc),
    end=datetime(2025, 1, 1, tzinfo=timezone.utc),
    adjustment="all",
)

bars_raw = client.get_stock_bars(request_raw).df.reset_index()
bars_adj = client.get_stock_bars(request_adj).df.reset_index()

print("=== 03 Corporate Action Adjustments (AAPL daily, 2020-2024) ===")
print(f"AAPL had a 4-for-1 split on 2020-08-28")
print(f"")

compare = bars_raw.merge(
    bars_adj,
    on="timestamp",
    suffixes=("_raw", "_adj"),
    how="outer",
)

compare["close_diff_pct"] = (
    (compare["close_adj"] - compare["close_raw"]) / compare["close_raw"] * 100
)

print("Comparing close prices around the 2020-08-28 split:")
aug = compare[
    (compare["timestamp"] >= "2020-08-20")
    & (compare["timestamp"] <= "2020-09-04")
]
cols = ["timestamp", "close_raw", "close_adj", "close_diff_pct"]
print(aug[cols].to_string(index=False))

print(f"\nPre-split (2020-08-27):")
row = aug[aug["timestamp"].dt.date == pd.Timestamp("2020-08-27").date()]
if not row.empty:
    print(f"  Raw close:     ${row['close_raw'].values[0]:.2f}")
    print(f"  Adjusted close: ${row['close_adj'].values[0]:.2f}")

print(f"\nPost-split (2020-08-31):")
row = aug[aug["timestamp"].dt.date == pd.Timestamp("2020-08-31").date()]
if not row.empty:
    print(f"  Raw close:     ${row['close_raw'].values[0]:.2f}")
    print(f"  Adjusted close: ${row['close_adj'].values[0]:.2f}")
