"""07_iex_vs_sip_volume.py — IEX feed volume vs. SIP (total market).

The free Alpaca tier uses IEX only, which captures a fraction of total US
market volume. This script fetches data and warns about volume reliability.
"""

from datetime import datetime, timezone

import pandas as pd
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config

cfg = load_config()
client = StockHistoricalDataClient(cfg.api_key, cfg.secret_key)

symbol = "SPY"

request = StockBarsRequest(
    symbol_or_symbols=symbol,
    timeframe=TimeFrame(1, TimeFrameUnit.Day),
    start=datetime(2024, 1, 1, tzinfo=timezone.utc),
    end=datetime(2024, 6, 1, tzinfo=timezone.utc),
)

bars = client.get_stock_bars(request)
df = bars.df.reset_index()

print("=== 07 IEX vs. SIP Volume Comparison (IEX only on free plan) ===")
print(f"Symbol: {symbol}")
print(f"Period: 2024-01-01 -> 2024-06-01")
print(f"Data source: IEX (Investors Exchange) - free tier")
print(f"")
print(f"NOTE: IEX volume is a fraction of total US market volume.")
print(f"SPY typically trades 60-100M shares/day across all exchanges.")
print(f"IEX captures roughly 2-4% of that.")
print(f"")

if not df.empty:
    print(f"Total trading days: {len(df)}")
    avg_volume = df["volume"].mean()
    max_volume = df["volume"].max()
    min_volume = df["volume"].min()
    print(f"Average daily volume (IEX): {avg_volume:,.0f}")
    print(f"Max daily volume (IEX):      {max_volume:,.0f}")
    print(f"Min daily volume (IEX):      {min_volume:,.0f}")

    estimated_sip_volume = avg_volume / 0.03
    print(f"\nEstimated true SIP daily volume (~3% capture): {estimated_sip_volume:,.0f}")

    print(f"\nIf your strategy uses volume-based indicators (VWAP, Volume Profile), ")
    print(f"these numbers will be skewed on the free plan. Consider upgrading to the ")
    print(f"unlimited plan for SIP data.")

    print(f"\nSample - first 5 days:")
    print(df[["timestamp", "close", "volume"]].head().to_string(index=False))
