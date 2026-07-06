"""08_retry_1min_fetch.py — Fetch 1-minute bars with exponential backoff retry.

Handles: connection drops, timeouts, rate limits (429), server errors (5xx).
Uses the same retry pattern as vinu_stock/providers/retry.py.
"""

import logging
import sys
from datetime import datetime, timedelta, timezone

import pandas as pd
from alpaca.common.exceptions import APIError
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from config import load_config
from retry import TransientError, retry_on_transient

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
LOG = logging.getLogger("fetch")


def build_client() -> StockHistoricalDataClient:
    cfg = load_config()
    return StockHistoricalDataClient(cfg.api_key, cfg.secret_key)


def is_retryable_api_error(exc: APIError) -> bool:
    status = exc.status_code
    # 429 = rate limit, 5xx = server hiccup
    return status in (429,) or (500 <= status < 600)


@retry_on_transient(
    n=4,
    backoff=2.0,
    exceptions=(
        ConnectionError,               # network dropped
        TimeoutError,                  # request timed out
        APIError,                      # 429 / 5xx (filtered below)
        TransientError,
    ),
)
def fetch_bars_with_retry(
    client: StockHistoricalDataClient,
    symbol: str,
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    try:
        request = StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame(1, TimeFrameUnit.Minute),
            start=start,
            end=end,
            limit=10000,
        )
        bars = client.get_stock_bars(request)
    except APIError as exc:
        if is_retryable_api_error(exc):
            LOG.warning("API error %s — retryable", exc.status_code)
            raise TransientError(str(exc)) from exc
        raise  # non-retryable (e.g. 400 bad request, 403 forbidden)

    df = bars.df.reset_index()
    if df.empty:
        raise TransientError(f"Empty response for {symbol}")

    return df


def main() -> None:
    if len(sys.argv) > 1:
        symbol = sys.argv[1].upper()
    else:
        symbol = "SPY"

    now = datetime.now(timezone.utc)
    # 15-min delay guard: never request data newer than 15 min ago
    safe_end = now - timedelta(minutes=15)
    start = safe_end - timedelta(days=5)

    LOG.info("Fetching 1m bars for %s", symbol)
    LOG.info("Range: %s  ->  %s", start, safe_end)

    client = build_client()

    try:
        df = fetch_bars_with_retry(client, symbol, start, safe_end)
    except Exception as exc:
        LOG.error("All retries exhausted: %s", exc)
        sys.exit(1)

    print(f"\n=== 08 Retry-enabled 1m Fetch: {symbol} ===")
    print(f"Bars returned: {len(df)}")
    print(f"Date range:    {df['timestamp'].min()}  ->  {df['timestamp'].max()}")
    print(f"Close range:   {df['close'].min():.2f}  ->  {df['close'].max():.2f}")
    print(f"Volume range:  {df['volume'].min():,.0f}  ->  {df['volume'].max():,.0f}")
    print(f"\nFirst 5 rows:")
    print(df.head(5).to_string(index=False))
    print(f"\nLast 5 rows:")
    print(df.tail(5).to_string(index=False))


if __name__ == "__main__":
    main()
