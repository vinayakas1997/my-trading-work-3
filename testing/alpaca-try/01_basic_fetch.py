"""01_basic_fetch.py — Fetch historical bars with auto-pagination.

Uses the alpaca-py SDK which handles next_page_token looping internally.
"""

from datetime import datetime, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config

cfg = load_config()

client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

request = StockBarsRequest(
    symbol_or_symbols="AAPL",
    timeframe=TimeFrame(1, TimeFrameUnit.Minute),
    start=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end=datetime(2025, 1, 1, tzinfo=timezone.utc),
    limit=10000,
)

bars = client.get_stock_bars(request)

df = bars.df.reset_index()

print("=== 01 Basic Fetch (AAPL 1m bars, 2023-2024) ===")
print(f"Total rows returned: {len(df)}")
print(f"Columns: {list(df.columns)}")
print("\nFirst 5 rows:")
print(df.head().to_string(index=False))
print("\nLast 5 rows:")
print(df.tail().to_string(index=False))
print(f"\nDate range: {df['timestamp'].min()}  ->  {df['timestamp'].max()}")
