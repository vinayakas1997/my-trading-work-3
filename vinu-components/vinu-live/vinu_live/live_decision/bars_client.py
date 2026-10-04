"""Shared live-bar fetch, used by both the poller (point 2, needs just
the latest bar's timestamp) and the detector (point 3, needs a full
trailing warmup window) -- one fetch function, not two, so both always
agree on field-name mapping (see the field-name note in
04-live-detector-schema.md: the raw route's timestamp column needs
mapping to `bar_ts` to match signal_evidence's convention).

Same route vinu_live/scheduler.py::_fetch_prices already calls
(GET /candles/{symbol} on vinu-stock-price) -- extended here rather than
duplicated, per that design doc's own note.
"""

from __future__ import annotations

import logging

import httpx
import pandas as pd

LOG = logging.getLogger(__name__)

# vinu-stock-price accepts 1m, 5m, 15m, 30m, 1h, 4h, 1d, 1wk. Strategy files say `schedule: daily`, which that service answers
# with HTTP 422 "Unsupported interval", so a daily strategy never received a single bar. Translate the words, keep the rest.
_INTERVAL_WORDS = {"daily": "1d", "day": "1d", "hourly": "1h", "weekly": "1wk", "week": "1wk", "1w": "1wk"}


def stock_interval(timeframe: str) -> str:
    key = (timeframe or "").strip().lower()
    return _INTERVAL_WORDS.get(key, key)


async def fetch_recent_bars(
    http: httpx.AsyncClient,
    stock_price_api_url: str,
    symbol: str,
    interval: str,
    limit: int,
    closed_only: bool = False,
) -> pd.DataFrame:
    """Returns a DataFrame with open/high/low/close/volume/bar_ts columns,
    most-recent bar last -- empty DataFrame on any fetch failure (fail
    honest, not fail with fabricated bars; callers must treat an empty
    result as "skip this cycle for this ticker", same posture
    scheduler.py's own price fetch already uses)."""
    try:
        resp = await http.get(
            f"{stock_price_api_url}/stock/candles/{symbol}",
            params={"interval": stock_interval(interval), "limit": limit, "adjusted": True, **({"closed_only": True} if closed_only else {})},
        )
        if resp.status_code != 200:
            LOG.warning("fetch_recent_bars(%s, %s): HTTP %s", symbol, interval, resp.status_code)
            return pd.DataFrame()
        rows = resp.json().get("data", [])
    except Exception as exc:
        LOG.warning("fetch_recent_bars(%s, %s) failed: %s", symbol, interval, exc)
        return pd.DataFrame()

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)
    # The raw route's timestamp column -- confirmed as "ts" on the
    # /quote endpoint (vinu_stock/service.py:302); signal_evidence's own
    # bars DataFrame expects "bar_ts". Map whichever one is actually
    # present rather than assuming, so this doesn't silently produce an
    # empty bar_ts column if the real field name differs.
    if "bar_ts" not in df.columns:
        for candidate in ("ts", "timestamp", "time"):
            if candidate in df.columns:
                df = df.rename(columns={candidate: "bar_ts"})
                break
    return df
