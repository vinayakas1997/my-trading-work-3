"""Seed stock data directly using alpaca SDK (which works)."""
from datetime import datetime, timezone, timedelta
import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
from pathlib import Path
import sqlite3, json, math

# Load keys
from dotenv import load_dotenv
import os
load_dotenv(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\vinu-stock-price\.env')

key = os.environ['ALPACA_API_KEY']
secret = os.environ['ALPACA_API_SECRET']
base_url = os.environ.get('ALPACA_DATA_BASE_URL', 'https://data.alpaca.markets')

client = StockHistoricalDataClient(key, secret, url_override=base_url)

symbols = ['AAPL', 'MSFT', 'TSLA', 'NVDA']
start = datetime(2022, 1, 1, tzinfo=timezone.utc)
end = datetime.now(timezone.utc)

# Fetch daily data for each symbol
for sym in symbols:
    print(f"\n=== {sym} ===")
    for interval_name, timeframe in [('1D', TimeFrame.Day)]:
        req = StockBarsRequest(
            symbol_or_symbols=sym,
            timeframe=TimeFrame(1, TimeFrameUnit.Day),
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(req)
        df = bars.df.reset_index()
        print(f'{interval_name}: {len(df)} rows')
        if len(df) > 0:
            print(f'  Range: {df["timestamp"].min()} to {df["timestamp"].max()}')
            print(f'  Close range: {df["close"].min():.2f} - {df["close"].max():.2f}')

print("\nDone. Data is available via alpaca SDK.")
