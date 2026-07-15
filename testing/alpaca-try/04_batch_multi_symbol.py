"""04_batch_multi_symbol.py — Fetch multiple symbols in one API call.

Batching keeps you under the 200 requests/min rate limit and is far
more efficient than looping over tickers one by one.
"""

from datetime import datetime, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config

cfg = load_config()
client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

symbols = ["AAPL", "MSFT", "SPY"]

request = StockBarsRequest(
    symbol_or_symbols=symbols,
    timeframe=TimeFrame(1, TimeFrameUnit.Day),
    start=datetime(2023, 1, 1, tzinfo=timezone.utc),
    end=datetime(2024, 1, 1, tzinfo=timezone.utc),
)

bars = client.get_stock_bars(request)
df = bars.df.reset_index()

print("=== 04 Batch Multi-Symbol Fetch (daily, 2023) ===")
print(f"Symbols: {symbols}")
print(f"Total rows: {len(df)}")
print(f"")

for sym in symbols:
    sub = df[df["symbol"] == sym]
    print(f"{sym}: {len(sub)} bars  |  {sub['close'].min():.2f} - {sub['close'].max():.2f}")

print(f"\nFirst 8 rows:")
print(df.head(8).to_string(index=False))
