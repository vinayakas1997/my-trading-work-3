from __future__ import annotations

from typing import Any

import pandas as pd

from vinu_simulator.clients.base import BaseClient


class PriceClient(BaseClient):
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

        all_dfs: list[pd.DataFrame] = []
        for sym in symbols:
            params: dict[str, Any] = {
                "interval": resolution,
                "from": from_ts,
                "to": to_ts,
            }
            try:
                resp = self.get(f"/candles/{sym}", params)
            except Exception:
                continue
            if not resp or "data" not in resp:
                continue
            records = resp["data"]
            if not records:
                continue
            df = pd.DataFrame(records)
            df["date"] = pd.to_datetime(df["bar_ts"], unit="s")
            df["symbol"] = sym
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
