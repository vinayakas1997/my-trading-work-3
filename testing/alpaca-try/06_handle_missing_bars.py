"""06_handle_missing_bars.py — Handle the "no trade, no bar" rule.

Illiquid stocks may have gaps in minute data. This script fetches data
for a less liquid symbol and demonstrates forward-filling the gaps.
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
    timeframe=TimeFrame(1, TimeFrameUnit.Minute),
    start=datetime(2024, 6, 10, tzinfo=timezone.utc),
    end=datetime(2024, 6, 14, tzinfo=timezone.utc),
)

bars = client.get_stock_bars(request)
df = bars.df.reset_index()

print("=== 06 Handling Missing Bars (No-Trade-No-Bar) ===")
print(f"Symbol: {symbol}")
print(f"Raw bars returned: {len(df)}")

if len(df) == 0:
    print("No data - symbol may be delisted or unavailable.")
else:
    df = df.set_index("timestamp")

    full_idx = pd.date_range(
        start=df.index.min(),
        end=df.index.max(),
        freq="1min",
    )

    df_reindexed = df.reindex(full_idx)
    missing_count = df_reindexed["close"].isna().sum()
    total_expected = len(full_idx)

    print(f"Expected bars (Mon-Fri 9:30-16:00 ET): ~{total_expected}")
    print(f"Actual bars present: {len(df)}")
    print(f"Missing bars (gaps): {missing_count}")
    print(f"Data completeness: {(1 - missing_count / total_expected) * 100:.1f}%")

    df_filled = df_reindexed.ffill()

    print(f"\nAfter forward-fill - NaNs remaining: {df_filled['close'].isna().sum()}")

    gap_seconds = df.index.to_series().diff().dt.total_seconds()
    print(f"\nLargest gap detected: {gap_seconds.max() / 60:.0f} minutes")
    print(f"Number of gaps > 1 min: {(gap_seconds > 60).sum()}")

    df_out = df.reset_index()
    print("\nFirst 5 rows after reindex + forward-fill:")
    print(df_filled.reset_index()[["index", "close"]].head(5).to_string(index=False))
