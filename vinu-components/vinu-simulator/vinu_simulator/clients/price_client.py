from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pandas as pd

from vinu_simulator.clients.base import BaseClient


class PriceClient(BaseClient):

    def get_ohclv(
        self,
        symbols: list[str],
        from_date: str,
        to_date: str,
        resolution: str = "1d",
        indicators: list[str] | None = None,
    ) -> dict[str, pd.DataFrame]:
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
            try:
                resp = self.get(f"/candles/{sym}", dict(params_template))
            except Exception:
                return sym, None
            if not resp or "data" not in resp:
                return sym, None
            records = resp["data"]
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
        return result

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

        return pivot_prices[symbols], pivot_volumes[symbols]
