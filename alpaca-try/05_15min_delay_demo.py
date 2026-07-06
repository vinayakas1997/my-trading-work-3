"""05_15min_delay_demo.py — Avoid the 15-minute data gap.

On the free plan, Alpaca delays historical data by 15 minutes.
Requesting data up to "now" will omit the last 15 minutes of bars.
Always set `end` to at least 15 minutes in the past.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config

cfg = load_config()
client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

now = datetime.now(timezone.utc)
safe_end = now - timedelta(minutes=15)

print("=== 05 15-Minute Delay Demo ===")
print(f"Current time (UTC):  {now}")
print(f"Safe end   (UTC):    {safe_end}")
print(f"Difference: ~{(now - safe_end).seconds // 60} minutes gap enforced")
print()

request_safe = StockBarsRequest(
    symbol_or_symbols="SPY",
    timeframe=TimeFrame(1, TimeFrameUnit.Minute),
    start=safe_end - timedelta(hours=2),
    end=safe_end,
)

bars = client.get_stock_bars(request_safe)
df = bars.df.reset_index()

if df.empty:
    print("No bars returned - the 15-min delay may be blocking recent data.")
else:
    print(f"Bars from {df['timestamp'].min()}  to  {df['timestamp'].max()}")
    print(f"Total bars in a ~2hr window: {len(df)} (expecting ~120)")
    print(f"\nLast 5 bars:")
    print(df.tail(5).to_string(index=False))
