from __future__ import annotations

import logging
from typing import Any

import httpx

from .unified_store import MemoryEntry, UnifiedMemoryStore, _now

LOG = logging.getLogger(__name__)


def _truncate(text: str, max_len: int = 2000) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + "..."


def _summarize_metrics(metrics: dict[str, Any]) -> str:
    parts = []
    for k in ("sharpe_ratio", "total_return", "max_drawdown", "win_rate"):
        v = metrics.get(k)
        if v is not None:
            if isinstance(v, float):
                if "return" in k or "drawdown" in k:
                    parts.append(f"{k}={v:.4%}")
                elif k == "win_rate":
                    parts.append(f"{k}={v:.1%}")
                else:
                    parts.append(f"{k}={v:.4f}")
            else:
                parts.append(f"{k}={v}")
    return ", ".join(parts)


class SyncService:
    def __init__(
        self,
        store: UnifiedMemoryStore,
        services_config: dict[str, str] | None = None,
    ) -> None:
        self._store = store
        self._config = services_config or {}

    # ------------------------------------------------------------------
    # Research runs
    # ------------------------------------------------------------------

    async def sync_research(self, symbol: str | None = None) -> int:
        url = self._config.get("vinu_research", "http://localhost:8087")
        params: dict[str, Any] = {"limit": 100}
        if symbol:
            params["symbol"] = symbol
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/research/runs", params=params)
                if resp.status_code != 200:
                    LOG.warning("sync_research: %s returned %d", url, resp.status_code)
                    return 0
                runs = resp.json()
        except Exception as e:
            LOG.warning("sync_research: failed to fetch from %s: %s", url, e)
            return 0

        entries: list[MemoryEntry] = []
        for run in runs:
            run_id = run.get("id")
            if not run_id:
                continue
            symbol_run = run.get("symbol", symbol or "")
            title = run.get("user_idea", f"Research run {run_id}")
            sharpe = run.get("best_sharpe", 0.0)
            dd = run.get("best_max_dd", 0.0)
            deflated = run.get("deflated_sharpe", 0.0)
            holdout = run.get("holdout_passed", None)
            stress = run.get("stress_test_passed", None)
            summary = f"Sharpe={sharpe:.4f}, MaxDD={dd:.4%}"
            if deflated:
                summary += f", DeflatedSharpe={deflated:.4f}"
            if holdout is not None:
                summary += f", Holdout={'PASS' if holdout else 'FAIL'}"
            if stress is not None:
                summary += f", Stress={'PASS' if stress else 'FAIL'}"
            content = _truncate(run.get("report_md", ""), 5000)

            entries.append(MemoryEntry(
                id=f"research-{run_id}",
                source="research",
                source_id=str(run_id),
                symbol=symbol_run,
                memory_type="research_run",
                title=title,
                content=content,
                summary=summary,
                metadata={
                    "best_sharpe": sharpe,
                    "best_max_dd": dd,
                    "deflated_sharpe": deflated,
                    "holdout_passed": holdout,
                    "stress_test_passed": stress,
                    "total_iterations": run.get("total_iterations", 0),
                    "status": run.get("status", ""),
                },
            ))

        self._store.clear_and_rebuild(source="research")
        count = self._store.bulk_add(entries)
        self._store.set_watermark("research")
        LOG.info("sync_research: %d entries synced", count)
        return count

    # ------------------------------------------------------------------
    # Research artifacts (active strategies)
    # ------------------------------------------------------------------

    async def sync_artifacts(self) -> int:
        url = self._config.get("vinu_research", "http://localhost:8087")
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{url}/research/artifacts",
                    params={"status": "ACTIVE,MONITORING"},
                )
                if resp.status_code != 200:
                    LOG.warning("sync_artifacts: %s returned %d", url, resp.status_code)
                    return 0
                artifacts = resp.json()
        except Exception as e:
            LOG.warning("sync_artifacts: failed to fetch from %s: %s", url, e)
            return 0

        entries: list[MemoryEntry] = []
        for art in artifacts:
            aid = art.get("artifact_id", "")
            if not aid:
                continue
            universe = art.get("universe", [])
            symbol = universe[0] if universe else ""
            sharpe = art.get("initial_sharpe", 0.0)
            status = art.get("status", "")
            summary = f"Artifact {aid}: Sharpe={sharpe:.4f}, Status={status}"
            entries.append(MemoryEntry(
                id=f"artifact-{aid}",
                source="research",
                source_id=aid,
                symbol=symbol,
                memory_type="strategy_artifact",
                title=f"Strategy {aid}",
                content="",
                summary=summary,
                metadata={
                    "artifact_id": aid,
                    "type": art.get("type", ""),
                    "status": status,
                    "initial_sharpe": sharpe,
                    "initial_max_dd": art.get("initial_max_dd"),
                    "deflated_sharpe": art.get("deflated_sharpe"),
                    "holdout_passed": art.get("holdout_passed"),
                    "universe": universe,
                },
            ))

        # Don't clear other research entries — artifacts coexist with runs
        count = self._store.bulk_add(entries)
        LOG.info("sync_artifacts: %d entries synced", count)
        return count

    # ------------------------------------------------------------------
    # Simulation runs
    # ------------------------------------------------------------------

    async def sync_simulator(self, symbol: str | None = None) -> int:
        url = self._config.get("vinu_simulator", "http://localhost:8085")
        params: dict[str, Any] = {}
        if symbol:
            params["symbol"] = symbol
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{url}/runs", params=params)
                if resp.status_code != 200:
                    LOG.warning("sync_simulator: %s returned %d", url, resp.status_code)
                    return 0
                runs = resp.json()
        except Exception as e:
            LOG.warning("sync_simulator: failed to fetch from %s: %s", url, e)
            return 0

        entries: list[MemoryEntry] = []
        for run in runs:
            run_id = run.get("run_id", "")
            if not run_id:
                continue
            strategy = run.get("strategy_name", "")
            metrics = run.get("metrics", {})
            summary = _summarize_metrics(metrics)
            symbols = run.get("symbols", [])
            sym = symbols[0] if symbols else symbol or ""
            validation = run.get("validation", {})
            mc = validation.get("monte_carlo", {}) if isinstance(validation, dict) else {}
            p_value = mc.get("p_value", None) if isinstance(mc, dict) else None
            meta: dict[str, Any] = {
                "strategy_name": strategy,
                "trade_count": run.get("trade_count"),
                "equity_points": run.get("equity_points"),
            }
            if p_value is not None:
                meta["mc_p_value"] = p_value
                summary += f", MC p={p_value}"

            entries.append(MemoryEntry(
                id=f"sim-{run_id}",
                source="simulator",
                source_id=run_id,
                symbol=sym,
                memory_type="simulation_run",
                title=f"Simulation: {strategy}",
                content="",
                summary=summary,
                metadata=meta,
            ))

        self._store.clear_and_rebuild(source="simulator")
        count = self._store.bulk_add(entries)
        self._store.set_watermark("simulator")
        LOG.info("sync_simulator: %d entries synced", count)
        return count

    # ------------------------------------------------------------------
    # Stock-price summary
    # ------------------------------------------------------------------

    async def sync_stock_price(self, symbol: str) -> int:
        url = self._config.get("vinu_stock_price", "http://localhost:8081")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{url}/candles/{symbol}",
                    params={"interval": "1d", "days": 30, "adjusted": True},
                )
                if resp.status_code != 200:
                    LOG.warning("sync_stock_price: %s returned %d", url, resp.status_code)
                    return 0
                data = resp.json().get("data", [])
        except Exception as e:
            LOG.warning("sync_stock_price: %s failed: %s", symbol, e)
            return 0

        if not data:
            return 0

        closes = [float(d.get("close", 0.0)) for d in data if d.get("close")]
        if len(closes) < 2:
            return 0

        start = closes[0]
        end = closes[-1]
        change = (end - start) / start if start else 0.0
        high = max(closes)
        low = min(closes)
        avg_vol = sum(
            float(d.get("volume", 0.0)) for d in data if d.get("volume")
        ) / len(data)
        summary = (
            f"{symbol}: {len(closes)} bars, "
            f"Close={end:.2f}, "
            f"Change={change:+.4%}, "
            f"High={high:.2f}, "
            f"Low={low:.2f}, "
            f"AvgVol={avg_vol:.0f}"
        )

        entry = MemoryEntry(
            id=f"price-{symbol}-{_now()[:10]}",
            source="stock_price",
            source_id=f"{symbol}-30d",
            symbol=symbol,
            memory_type="price_summary",
            title=f"Price summary: {symbol}",
            content="",
            summary=summary,
            metadata={
                "last_close": end,
                "change_pct": change,
                "high": high,
                "low": low,
                "avg_volume": avg_vol,
                "bar_count": len(closes),
            },
        )
        self._store.clear_and_rebuild(source="stock_price")
        self._store.add_entry(entry)
        self._store.set_watermark("stock_price")
        LOG.info("sync_stock_price: %s synced (%d bars)", symbol, len(closes))
        return 1

    # ------------------------------------------------------------------
    # News
    # ------------------------------------------------------------------

    async def sync_news(self, symbol: str, limit: int = 50) -> int:
        url = self._config.get("vinu_news", "http://localhost:8080")
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    f"{url}/search",
                    params={"q": symbol, "limit": limit},
                )
                if resp.status_code != 200:
                    LOG.warning("sync_news: %s returned %d", url, resp.status_code)
                    return 0
                articles = resp.json()
        except Exception as e:
            LOG.warning("sync_news: %s failed: %s", symbol, e)
            return 0

        if not articles:
            return 0

        if isinstance(articles, dict):
            articles = articles.get("results", articles.get("articles", []))

        entries: list[MemoryEntry] = []
        for i, art in enumerate(articles):
            if isinstance(art, str):
                continue
            headline = art.get("title", art.get("headline", f"News {i}"))
            snippet = art.get("summary", art.get("snippet", ""))
            url_art = art.get("url", art.get("link", ""))
            published = art.get("published_at", art.get("date", ""))
            sentiment = art.get("sentiment", None)
            meta: dict[str, Any] = {"url": url_art, "published": published}
            if sentiment is not None:
                meta["sentiment"] = sentiment

            entries.append(MemoryEntry(
                id=f"news-{symbol}-{_now()[:10]}-{i}",
                source="news",
                source_id="",
                symbol=symbol,
                memory_type="news_article",
                title=headline,
                content=_truncate(snippet, 3000),
                summary=snippet[:200] if snippet else headline[:200],
                metadata=meta,
            ))

        if entries:
            self._store.clear_and_rebuild(source="news")
            count = self._store.bulk_add(entries)
            self._store.set_watermark("news")
            LOG.info("sync_news: %d articles synced for %s", count, symbol)
            return count
        return 0

    # ------------------------------------------------------------------
    # Full sync for a symbol
    # ------------------------------------------------------------------

    async def sync_symbol(self, symbol: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        counts["research"] = await self.sync_research(symbol)
        counts["artifacts"] = await self.sync_artifacts()
        counts["simulator"] = await self.sync_simulator(symbol)
        counts["stock_price"] = await self.sync_stock_price(symbol)
        counts["news"] = await self.sync_news(symbol)
        return counts

    async def sync_all(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        counts["research"] = await self.sync_research()
        counts["artifacts"] = await self.sync_artifacts()
        counts["simulator"] = await self.sync_simulator()
        return counts
