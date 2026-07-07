from __future__ import annotations

from typing import Any

from vinu_correlation.cache import CorrelationCache
from vinu_correlation.clients.news_client import NewsClient
from vinu_correlation.clients.price_client import PriceClient
from vinu_correlation.config import VinuCorrelationConfig, load_config
from vinu_correlation.engine.baseline import compute_baseline, classify_deviation
from vinu_correlation.engine.correlation import (
    compute_correlation,
    compute_lag_analysis,
    resample_news_to_hourly,
    resample_returns_to_hourly,
)
from vinu_correlation.engine.drawdown import attribute_drawdown, get_drawdowns
from vinu_correlation.engine.granger import run_granger_causality_test as test_granger_causality
from vinu_correlation.engine.impact import (
    aggregate_by_thread,
    compute_impact_for_article,
    parse_tickers,
)
from vinu_correlation.engine.market_hours import IMPACT_WINDOWS, classify_session
from vinu_correlation.storage.backend import CorrelationStorage


class CorrelationAPI:
    def __init__(self, config: VinuCorrelationConfig | None = None):
        self._config = config or load_config()
        self._news_client = NewsClient(self._config.news_api_url)
        self._price_client = PriceClient(self._config.stock_api_url)
        self._storage = CorrelationStorage(self._config.data_root)
        self._cache = CorrelationCache(
            maxsize=self._config.cache_maxsize,
            ttl=self._config.cache_ttl_sec,
        )

    def get_impact(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any]:
        cached = self._cache.get_impact(symbol, from_ts, to_ts)
        if cached is not None:
            return cached

        if from_ts is not None and to_ts is not None:
            articles = self._news_client.get_ticker_news(symbol, from_ts=from_ts, to_ts=to_ts)
        else:
            articles = self._news_client.get_ticker_news(symbol, days=30)
        if not articles:
            result = {
                "symbol": symbol,
                "high_impact_bearish_events": 0,
                "high_impact_bullish_events": 0,
                "avg_price_drop_30m": 0.0,
                "event_count": 0,
                "events": [],
            }
            self._cache.set_impact(symbol, from_ts, to_ts, result)
            return result

        events = []
        for article in articles:
            article_events = compute_impact_for_article(
                article,
                self._price_client,
                impact_high_threshold=self._config.impact_high_threshold,
                impact_medium_threshold=self._config.impact_medium_threshold,
            )
            events.extend(article_events)

        bearish_high = [e for e in events if e.get("impact_label") == "high_bearish"]
        bullish_high = [e for e in events if e.get("impact_label") == "high_bullish"]
        price_drops = [e.get("price_change_30m") or 0 for e in bearish_high]
        avg_drop = sum(price_drops) / len(price_drops) if price_drops else 0.0

        result = {
            "symbol": symbol,
            "high_impact_bearish_events": len(bearish_high),
            "high_impact_bullish_events": len(bullish_high),
            "avg_price_drop_30m": round(avg_drop, 2),
            "event_count": len(events),
            "events": events,
        }
        self._cache.set_impact(symbol, from_ts, to_ts, result)
        return result

    def get_events(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> list[dict[str, Any]]:
        result = self.get_impact(symbol, from_ts, to_ts)
        return result.get("events", [])

    def get_correlation(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any]:
        cached = self._cache.get_correlation(symbol, from_ts, to_ts)
        if cached is not None:
            return cached

        if from_ts is not None and to_ts is not None:
            articles = self._news_client.get_ticker_news(symbol, from_ts=from_ts, to_ts=to_ts)
        else:
            articles = self._news_client.get_ticker_news(symbol, days=30)
        candles = self._price_client.get_candles(symbol, from_ts=from_ts, to_ts=to_ts)

        news_hourly = resample_news_to_hourly(articles)
        returns_hourly = resample_returns_to_hourly(candles)

        corr = compute_correlation(news_hourly, returns_hourly)
        lag = compute_lag_analysis(news_hourly, returns_hourly)

        news_series = news_hourly.set_index("hour_ts")["article_count"]
        return_series = returns_hourly.set_index("hour_ts")["return"]
        granger = test_granger_causality(news_series, return_series)

        result = {
            "symbol": symbol,
            "news_return_corr": corr["news_return_corr"],
            "corr_p_value": corr["corr_p_value"],
            "corr_ci_lower": corr["corr_ci_lower"],
            "corr_ci_upper": corr["corr_ci_upper"],
            "sample_size": corr["sample_size"],
            "sentiment_return_corr": corr["sentiment_return_corr"],
            "news_volume_corr": corr["news_volume_corr"],
            "granger_p_value": granger["p_value"],
            "granger_causes_prices": granger["granger_causes_prices"],
            "best_lag_minutes": lag["best_lag_minutes"],
            "best_lag_correlation": lag["best_lag_correlation"],
            "lag_results": lag["lag_results"],
        }
        self._cache.set_correlation(symbol, from_ts, to_ts, result)
        return result

    def get_drawdown(
        self,
        symbol: str,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ) -> dict[str, Any]:
        cached = self._cache.get_drawdown(symbol, from_ts, to_ts)
        if cached is not None:
            return cached

        candles = self._price_client.get_candles(symbol, from_ts=from_ts, to_ts=to_ts)
        if from_ts is not None and to_ts is not None:
            articles = self._news_client.get_ticker_news(symbol, from_ts=from_ts, to_ts=to_ts)
        else:
            articles = self._news_client.get_ticker_news(symbol, days=30)

        events = []
        for article in articles:
            events.extend(
                compute_impact_for_article(article, self._price_client)
            )

        drawdowns_found = get_drawdowns(
            symbol, candles,
            from_ts=from_ts, to_ts=to_ts,
            drop_threshold_pct=self._config.drawdown_min_pct,
            lookback_hours=self._config.drawdown_lookback_hours,
        )

        attributed = []
        for dd in drawdowns_found:
            attr = attribute_drawdown(symbol, dd["peak_ts"], dd["trough_ts"], events)
            attr["drop_pct"] = dd["drop_pct"]
            attributed.append(attr)

        result = {
            "symbol": symbol,
            "drawdown_count": len(attributed),
            "drawdowns": attributed,
        }
        self._cache.set_drawdown(symbol, from_ts, to_ts, result)
        return result

    def get_baseline(self, symbol: str, *, days: int = 30) -> dict[str, Any]:
        articles = self._news_client.get_ticker_news(symbol, days=days)
        baselines = compute_baseline(
            articles,
            window_days=self._config.baseline_window_days,
        )

        by_session: dict[str, dict] = {}
        for b in baselines:
            sess = b["session"]
            if sess not in by_session:
                by_session[sess] = {"counts": [], "mean": 0, "stddev": 0}
            by_session[sess]["counts"].append(b["article_count"])

        for sess, data in by_session.items():
            counts = data["counts"]
            data["mean"] = round(sum(counts) / len(counts), 2) if counts else 0.0
            data["stddev"] = round(
                (sum((c - data["mean"]) ** 2 for c in counts) / len(counts)) ** 0.5, 2
            ) if counts else 1.0

        current_hour = int(__import__("time").time() / 3600) * 3600
        current_counts = {
            b["session"]: b["article_count"]
            for b in baselines if abs(b["hour_ts"] - current_hour) < 3600
        }

        z_scores = {}
        for sess, data in by_session.items():
            curr = current_counts.get(sess, 0)
            if data["stddev"]:
                z_scores[sess] = round((curr - data["mean"]) / data["stddev"], 2)
            else:
                z_scores[sess] = 0.0

        result = {
            "symbol": symbol,
            "mean_daily_articles": round(
                sum(data["mean"] for data in by_session.values()), 2
            ),
            "sessions": {
                sess: {
                    "mean": data["mean"],
                    "stddev": data["stddev"],
                    "z_score": z_scores.get(sess, 0),
                    "deviation_level": classify_deviation(z_scores.get(sess, 0)),
                }
                for sess, data in by_session.items()
            },
        }
        return result

    def compute_and_store(
        self,
        symbol: str,
        incremental: bool = True,
        from_ts: int | None = None,
        to_ts: int | None = None,
    ):
        if incremental:
            last_ts = self._storage.get_last_computed_ts(symbol)
        else:
            last_ts = None

        if from_ts is not None and to_ts is not None:
            articles = self._news_client.get_ticker_news(symbol, from_ts=from_ts, to_ts=to_ts)
        else:
            articles = self._news_client.get_ticker_news(symbol, days=30)
        if not articles:
            return

        all_events = []
        for article in articles:
            events = compute_impact_for_article(
                article,
                self._price_client,
                impact_high_threshold=self._config.impact_high_threshold,
                impact_medium_threshold=self._config.impact_medium_threshold,
            )
            all_events.extend(events)

        self._storage.append_events(symbol, all_events)

        baselines = compute_baseline(articles, window_days=self._config.baseline_window_days)
        for b in baselines:
            b["symbol"] = symbol
        self._storage.append_baselines(symbol, baselines)
        self._cache.invalidate(symbol)
