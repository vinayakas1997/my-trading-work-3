"""ResearchService facade — wraps the research loop with persistence, lifecycle, and health."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from vinu_research.config import ResearchConfig, load_config
from vinu_research.storage import ResearchStorage
from vinu_research.storage.models import ResearchRunRecord, STATUS_DONE, STATUS_FAILED, STATUS_PENDING, STATUS_RUNNING
from vinu_research.storage.sqlite_backend import ResearchStorage

LOG = logging.getLogger(__name__)


class ResearchService:
    def __init__(
        self,
        config: ResearchConfig | None = None,
        storage: ResearchStorage | None = None,
    ) -> None:
        self._config = config or load_config()
        self._storage = storage or ResearchStorage(
            self._config.data_root / "research_meta.db"
        )
        self._owns_storage = storage is None

    @property
    def config(self) -> ResearchConfig:
        return self._config

    @property
    def storage(self) -> ResearchStorage:
        return self._storage

    async def run_research(
        self,
        user_idea: str,
        symbol: str,
        from_date: str,
        to_date: str,
        indicators: list[str] | None = None,
        initial_capital: float | None = None,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        record = ResearchRunRecord(
            user_idea=user_idea,
            symbol=symbol.upper(),
            from_date=from_date,
            to_date=to_date,
            status=STATUS_PENDING,
        )
        if not dry_run:
            record = self._storage.insert_run(record)
            record.status = STATUS_RUNNING
            self._storage.update_run(record)
        else:
            record.id = -1

        try:
            from vinu_research.tools import ResearchTools
            from vinu_research.loop import StrategyResearchLoop

            tools = ResearchTools(self._config)
            loop = StrategyResearchLoop(
                tools=tools,
                config=self._config,
            )
            result = await loop.run(
                user_idea=user_idea,
                symbol=symbol,
                from_date=from_date,
                to_date=to_date,
                indicators=indicators,
                initial_capital=initial_capital or self._config.initial_capital,
            )

            if not dry_run:
                record.status = STATUS_DONE
                record.total_iterations = result.total_iterations
                record.best_iteration = result.best_iteration or -1
                if result.best_result:
                    record.best_sharpe = result.best_result.metrics.sharpe_ratio
                    record.best_max_dd = result.best_result.metrics.max_drawdown
                record.report_md = result.report_md or ""
                self._storage.update_run(record)

            return {
                "id": record.id,
                "user_idea": user_idea,
                "symbol": symbol,
                "from_date": from_date,
                "to_date": to_date,
                "status": record.status,
                "total_iterations": result.total_iterations,
                "best_iteration": result.best_iteration,
                "best_sharpe": record.best_sharpe,
                "best_max_dd": record.best_max_dd,
                "report_md": result.report_md,
            }
        except Exception as e:
            LOG.warning("Research failed: %s", e, exc_info=True)
            if not dry_run:
                record.status = STATUS_FAILED
                record.error_message = str(e)
                self._storage.update_run(record)
            raise

    def list_runs(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        return [r.to_dict() for r in self._storage.list_runs(symbol, status, limit)]

    def get_run(self, run_id: int) -> dict[str, Any] | None:
        r = self._storage.get_run(run_id)
        return r.to_dict() if r else None

    def delete_run(self, run_id: int) -> bool:
        return self._storage.delete_run(run_id)

    def health(self) -> dict[str, Any]:
        deps: dict[str, dict] = {}
        for name, url in [
            ("simulator", self._config.simulator_api_url),
            ("features", self._config.features_api_url),
            ("correlation", self._config.correlation_api_url),
        ]:
            try:
                res = httpx.get(f"{url}/health", timeout=2.0)
                deps[name] = {"reachable": True, "status_code": res.status_code}
            except Exception as e:
                deps[name] = {"reachable": False, "error": str(e)}
        info = self._storage.health_info()
        info["dependencies"] = deps
        info["service"] = "vinu-research"
        info["version"] = "0.1.0"
        return info

    def close(self) -> None:
        if self._owns_storage:
            self._storage.close()

    def __enter__(self) -> ResearchService:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()
