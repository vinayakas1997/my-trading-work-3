from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
from typing import Any

import pandas as pd

from vinu_simulator.clients._cache import LRUCache
from vinu_simulator.clients.base import BaseClient


LOG = logging.getLogger(__name__)


_PAGE_LIMIT = 50_000
_MAX_PAGES = 20

class PriceClient(BaseClient):

    def __init__(self, base_url: str, timeout: float = 30.0, cache_maxsize: int = 256):
        super().__init__(base_url, timeout=timeout)
        # item #13 finding #4: one cache per fetch shape (get_ohclv's
        # per-symbol DataFrame dict vs _fetch_price_data's stacked
        # long-format frame) -- same symbol/date-range request key would
        # otherwise collide across two incompatible return shapes.
        self._ohclv_cache = LRUCache(maxsize=cache_maxsize)
        self._price_data_cache = LRUCache(maxsize=cache_maxsize)

    def get_ohclv(
        self,
        symbols: list[str],
        from_date: str,
        to_date: str,
        resolution: str = "1d",
        indicators: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
        # Not case-normalized: `sym` is passed through verbatim into the
        # real `/candles/{sym}` request, so a case difference is a
        # different real request, not a cache-equivalent one.
        cache_key = (
            tuple(sorted(symbols)), from_date, to_date,
            resolution, tuple(sorted(indicators or [])),
        )
        cached = self._ohclv_cache.get(cache_key)
        if cached is not None:
            return {sym: df.copy() for sym, df in cached.items()}

        from_ts = int(pd.Timestamp(from_date).timestamp())
        to_ts = int(pd.Timestamp(to_date).timestamp())

        params_template: dict[str, Any] = {
            "interval": resolution,
            "from": from_ts,
            "to": to_ts,
            "adjusted": True,
        }
        if indicators:
            params_template["indicators"] = ",".join(indicators)

        result: dict[str, pd.DataFrame] = {}
        max_workers = min(len(symbols), 8)

        def _fetch(sym: str) -> tuple[str, pd.DataFrame | None]:
            # The price service caps one response; it says so (`truncated`, `next_from`). Follow the pages, or a long
            # 15-minute window was silently backtested on only its oldest 5,000 bars.
            params = dict(params_template, limit=_PAGE_LIMIT)
            records: list[dict] = []
            for _page in range(_MAX_PAGES):
                try:
                    resp = self.get(f"/candles/{sym}", dict(params))
                except Exception as exc:
                    LOG.warning("get_ohclv: %s %s..%s fetch failed: %r", sym, from_date, to_date, exc)
                    return sym, None
                if not resp or "data" not in resp:
                    return sym, None
                records.extend(resp["data"])
                if not resp.get("truncated") or not resp.get("next_from"):
                    break
                params["from"] = resp["next_from"]
            else:
                LOG.warning("get_ohclv: %s %s..%s still truncated after %d pages", sym, from_date, to_date, _MAX_PAGES)
                return sym, None            # an incomplete history must not be backtested as if it were complete
            if not records:
                return sym, None
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["bar_ts"], unit="s")
            df = df.set_index("date").sort_index()
            keep = ["open", "high", "low", "close", "volume"] + (indicators or [])
            keep = [c for c in keep if c in df.columns]
            return sym, df[keep]

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch, sym): sym for sym in symbols}
            for future in as_completed(futures):
                sym, df = future.result()
                if df is not None:
                    result[sym] = df
        # Cache only a complete answer. A failed or empty fetch used to be
        # cached with no expiry, so one transient failure made every later
        # call for that range return "no data" without asking the stock API.
        if set(symbols) <= set(result):
            self._ohclv_cache.set(cache_key, result)
        return {sym: df.copy() for sym, df in result.items()}

    def get_prices(
        self,
        symbols: list[str],
        from_date: str,
        to_date: str,
        resolution: str = "1d",
    ) -> pd.DataFrame:
        prices, _ = self._fetch_price_data(symbols, from_date, to_date, resolution)
        return prices

    def get_price_and_volume(
        self,
        symbols: list[str],
        from_date: str,
        to_date: str,
        resolution: str = "1d",
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        return self._fetch_price_data(symbols, from_date, to_date, resolution)

    def _fetch_price_data(
        self,
        symbols: list[str],
        from_date: str,
        to_date: str,
        resolution: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        # Exact requested order, NOT sorted -- unlike get_ohclv's dict-keyed
        # cache, the two DataFrames returned here are column-selected via
        # `pivot_prices[symbols]` in this exact order, so a differently
        # ordered request must miss (and refetch) rather than return
        # mis-ordered columns from a cache hit.
        cache_key = (tuple(symbols), from_date, to_date, resolution)
        cached = self._price_data_cache.get(cache_key)
        if cached is not None:
            return cached[0].copy(), cached[1].copy()

        from_ts = int(pd.Timestamp(from_date).timestamp())
        to_ts = int(pd.Timestamp(to_date).timestamp())

        params_template: dict[str, Any] = {
            "interval": resolution,
            "from": from_ts,
            "to": to_ts,
            "adjusted": True,
        }

        all_dfs: list[pd.DataFrame] = []
        max_workers = min(len(symbols), 8)

        def _fetch(sym: str) -> pd.DataFrame | None:
            try:
                resp = self.get(f"/candles/{sym}", dict(params_template))
            except Exception:
                return None
            if not resp or "data" not in resp:
                return None
            records = resp["data"]
            if not records:
                return None
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["bar_ts"], unit="s")
            df["symbol"] = sym
            return df

        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {pool.submit(_fetch, sym): sym for sym in symbols}
            for future in as_completed(futures):
                df = future.result()
                if df is not None:
                    all_dfs.append(df)

        if not all_dfs:
            raise ValueError(
                f"No price data found for any of {symbols} "
                f"in range {from_date} to {to_date}"
            )

        combined = pd.concat(all_dfs, ignore_index=True)
        price_col = "close"
        volume_col = "volume"

        pivot_prices = combined.pivot_table(
            index="date",
            columns="symbol",
            values=price_col,
            aggfunc="last",
        ).sort_index()
        pivot_volumes = combined.pivot_table(
            index="date",
            columns="symbol",
            values=volume_col,
            aggfunc="last",
        ).sort_index()

        missing = [s for s in symbols if s not in pivot_prices.columns]
        if missing:
            raise ValueError(
                f"Tickers missing from price data: {missing}. "
                f"Available: {list(pivot_prices.columns)}"
            )

        result = (pivot_prices[symbols], pivot_volumes[symbols])
        self._price_data_cache.set(cache_key, result)
        return result[0].copy(), result[1].copy()
