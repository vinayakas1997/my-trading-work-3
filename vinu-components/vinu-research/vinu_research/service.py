from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from vinu_research.config import ResearchConfig, load_config
from vinu_research.loop import StrategyResearchLoop
from vinu_research.storage import ResearchStorage
from vinu_research.storage.models import ResearchRunRecord, STATUS_DONE, STATUS_FAILED, STATUS_PENDING, STATUS_RUNNING
from vinu_research.tools import ResearchTools

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
        self._http = httpx.AsyncClient(timeout=5.0)

    @property
    def config(self) -> ResearchConfig:
        return self._config

    @property
    def storage(self) -> ResearchStorage:
        return self._storage

    async def _run_in_thread(self, func, *args, **kwargs):
        return await asyncio.to_thread(func, *args, **kwargs)

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

        if dry_run:
            return {
                "id": -1,
                "user_idea": user_idea,
                "symbol": symbol.upper(),
                "from_date": from_date,
                "to_date": to_date,
                "status": "dry_run",
                "total_iterations": 0,
                "best_iteration": -1,
                "best_sharpe": 0.0,
                "best_max_dd": 0.0,
                "report_md": "",
            }

        record = await self._run_in_thread(self._storage.insert_run, record)
        record.status = STATUS_RUNNING
        await self._run_in_thread(self._storage.update_run, record)

        try:
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

            record.status = STATUS_DONE
            record.total_iterations = result.total_iterations
            record.best_iteration = result.best_iteration or -1
            if result.best_result:
                record.best_sharpe = result.best_result.metrics.sharpe_ratio
                record.best_max_dd = result.best_result.metrics.max_drawdown
            record.report_md = result.report_md or ""
            await self._run_in_thread(self._storage.update_run, record)

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
            record.status = STATUS_FAILED
            record.error_message = str(e)
            await self._run_in_thread(self._storage.update_run, record)
            raise

    async def list_runs(
        self,
        symbol: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        runs = await self._run_in_thread(self._storage.list_runs, symbol, status, limit)
        return [r.to_dict() for r in runs]

    async def get_run(self, run_id: int) -> dict[str, Any] | None:
        r = await self._run_in_thread(self._storage.get_run, run_id)
        return r.to_dict() if r else None

    async def approve_run(self, run_id: int) -> dict[str, Any] | None:
        result = await self._run_in_thread(self._storage.approve_run, run_id)
        return result.to_dict() if result else None

    async def delete_run(self, run_id: int) -> bool:
        return await self._run_in_thread(self._storage.delete_run, run_id)

    async def health(self) -> dict[str, Any]:
        deps: dict[str, dict] = {}
        for name, url in [
            ("simulator", self._config.simulator_api_url),
            ("features", self._config.features_api_url),
            ("correlation", self._config.correlation_api_url),
        ]:
            try:
                res = await self._http.get(f"{url}/health")
                deps[name] = {"reachable": True, "status_code": res.status_code}
            except Exception as e:
                deps[name] = {"reachable": False, "error": str(e)}
        info = await self._run_in_thread(self._storage.health_info)
        info["dependencies"] = deps
        info["service"] = "vinu-research"
        info["version"] = "0.1.0"
        return info

    async def close(self) -> None:
        if self._owns_storage:
            await self._run_in_thread(self._storage.close)
        await self._http.aclose()

    async def __aenter__(self) -> ResearchService:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
