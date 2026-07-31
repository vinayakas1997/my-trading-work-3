from __future__ import annotations

from pathlib import Path
from typing import Any

from vinu_initial_analysis.cache import CorrelationCache
from vinu_initial_analysis.clients.news_client import NewsClient
from vinu_initial_analysis.clients.price_client import PriceClient
from vinu_initial_analysis.config import VinuInitialAnalysisConfig, load_config
from vinu_initial_analysis.runner import AngleRunner
from vinu_initial_analysis.storage.meta import RunLog
from vinu_initial_analysis.storage.parquet import AngleStorage


class CorrelationAPI:
    """Backward-compatible API that delegates to the angle runner + storage."""

    def __init__(self, config: VinuInitialAnalysisConfig | None = None):
        self._config = config or load_config()
        self._news_client = NewsClient(self._config.news_api_url)
        self._price_client = PriceClient(self._config.stock_api_url)
        self._storage = AngleStorage(self._config.data_root)
        self._run_log = RunLog(self._config.data_root / "runs.db")
        self._runner = AngleRunner(self._storage, self._run_log, news_client=self._news_client, price_client=self._price_client)
        self._cache = CorrelationCache(
            maxsize=self._config.cache_maxsize,
            ttl=self._config.cache_ttl_sec,
        )

    @property
    def storage(self) -> AngleStorage:
        return self._storage

    @property
    def runner(self) -> AngleRunner:
        return self._runner

    # -- run all angles for a symbol ---------------------------------------

    def compute_and_store(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
        angle_names: list[str] | None = None,
    ) -> dict[str, Any]:
        return self._runner.run(symbol, from_ts=from_ts, to_ts=to_ts, angle_names=angle_names)

    # -- backward-compat single-angle query methods ------------------------
    # These read from the new parquet storage.
    # The angle-specific data is stored per-angle; we load and reshape.

    def get_impact(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any]:
        cached = self._cache.get_impact(symbol, from_ts, to_ts)
        if cached is not None:
            return cached
        df = self._storage.read(symbol, "news_price_causality")
        if df.empty:
            result = {
                "symbol": symbol,
                "high_impact_bearish_events": 0,
                "high_impact_bullish_events": 0,
                "avg_price_drop_30m": 0.0,
                "event_count": 0,
                "events": [],
            }
        else:
            records = df.to_dict("records")
            bearish = [e for e in records if e.get("impact_label") == "high_bearish"]
            bullish = [e for e in records if e.get("impact_label") == "high_bullish"]
            avg_drop = (
                sum(e.get("price_change_30m") or 0 for e in bearish) / len(bearish)
                if bearish else 0.0
            )
            result = {
                "symbol": symbol,
                "high_impact_bearish_events": len(bearish),
                "high_impact_bullish_events": len(bullish),
                "avg_price_drop_30m": round(avg_drop, 2),
                "event_count": len(records),
                "events": records,
            }
        self._cache.set_impact(symbol, from_ts, to_ts, result)
        return result

    def get_events(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> list[dict[str, Any]]:
        return self.get_impact(symbol, from_ts, to_ts).get("events", [])

    def get_correlation(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        cached = self._cache.get_correlation(symbol, from_ts, to_ts)
        if cached is not None:
            return cached
        df = self._storage.read(symbol, "news_price_causality", filters=[("type", "=", "correlation")])
        if df.empty:
            result = {"symbol": symbol, "news_return_corr": None, "sample_size": 0}
        else:
            # Rows are written per time_format (15min, 1H, 1D); the 1D
            # correlation is often NaN (daily bars at midnight UTC barely
            # overlap news hours). Surface the best-sampled time format
            # instead of the last-written row (Bug-5).
            records = sorted(
                df.to_dict("records"),
                key=lambda r: (r.get("sample_size") or 0),
                reverse=True,
            )
            best = records[0]
            result = {
                "symbol": symbol,
                "news_return_corr": best.get("news_return_corr"),
                "sample_size": best.get("sample_size", 0),
            }
        self._cache.set_correlation(symbol, from_ts, to_ts, result)
        return result

    def get_drawdown(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        cached = self._cache.get_drawdown(symbol, from_ts, to_ts)
        if cached is not None:
            return cached
        df = self._storage.read(symbol, "drawdown_deep_dive")
        result = {
            "symbol": symbol,
            "drawdown_count": len(df),
            "drawdowns": df.to_dict("records") if not df.empty else [],
        }
        self._cache.set_drawdown(symbol, from_ts, to_ts, result)
        return result

    def get_story(self, symbol: str, from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        impact = self.get_impact(symbol, from_ts, to_ts)
        corr = self.get_correlation(symbol, from_ts, to_ts)
        dd = self.get_drawdown(symbol, from_ts, to_ts)
        return {
            "ticker": symbol,
            "period": {"from": from_ts, "to": to_ts},
            "impact_events": impact.get("events", []),
            "correlations": corr,
            "drawdown_events": dd.get("drawdowns", []),
        }

    def get_batch(self, symbols: list[str], from_ts: int | None = None, to_ts: int | None = None) -> dict[str, Any]:
        results = {}
        for sym in symbols:
            try:
                results[sym] = self.get_story(sym, from_ts, to_ts)
            except Exception as e:
                results[sym] = {"error": str(e)}
        return {"symbols": symbols, "results": results, "count": len(symbols)}

    def close(self) -> None:
        """Close resources such as the database connection."""
        if hasattr(self, "_run_log"):
            self._run_log.close()

