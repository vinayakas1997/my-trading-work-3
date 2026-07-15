"""02_timezone_aware.py — Force America/New_York timezone.

Alpaca returns UTC timestamps. If you use your local machine timezone when
defining start/end, you may truncate part of the trading day. This script
forces Eastern Time to ensure full market hours are captured.
"""

from datetime import datetime

import pandas as pd
import pytz
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config

cfg = load_config()
client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

eastern = pytz.timezone("America/New_York")

start_et = eastern.localize(datetime(2023, 1, 2, 9, 30, 0))
end_et = eastern.localize(datetime(2023, 1, 6, 16, 0, 0))

start_utc = start_et.astimezone(pytz.UTC)
end_utc = end_et.astimezone(pytz.UTC)

print("=== 02 Timezone-Aware Fetch (MSFT, Jan 2-6 2023) ===")
print(f"Start (ET):  {start_et}")
print(f"Start (UTC): {start_utc}")
print(f"End   (ET):  {end_et}")
print(f"End   (UTC): {end_utc}")

request = StockBarsRequest(
    symbol_or_symbols="MSFT",
    timeframe=TimeFrame(1, TimeFrameUnit.Minute),
    start=start_utc,
    end=end_utc,
)

bars = client.get_stock_bars(request)
df = bars.df.reset_index()

print(f"\nTotal bars: {len(df)}")
print(f"First timestamp (UTC):   {df['timestamp'].min()}")
print(f"Last  timestamp (UTC):   {df['timestamp'].max()}")

df["timestamp_et"] = df["timestamp"].dt.tz_convert(eastern)
print(f"First timestamp (ET):    {df['timestamp_et'].min()}")
print(f"Last  timestamp (ET):    {df['timestamp_et'].max()}")

print("\nFirst 3 rows (ET):")
cols = ["symbol", "timestamp_et", "open", "high", "low", "close", "volume"]
print(df[cols].head(3).to_string(index=False))
