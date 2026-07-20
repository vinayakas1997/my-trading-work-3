from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from vinu_research.config import ResearchConfig, load_config
from vinu_research.loop import StrategyResearchLoop
from vinu_research.llm import ResearchLlmClient
from vinu_research.llm_generator import LlmStrategyGenerator
from vinu_research.models import Artifact, ArtifactStatus, BenchEntry
from vinu_research.storage import ResearchStorage
from vinu_research.storage.models import ResearchRunRecord, STATUS_DONE, STATUS_FAILED, STATUS_PENDING, STATUS_RUNNING
from vinu_research.storage.strategy_store import SqliteStrategyStore
from vinu_research.tools import ResearchTools
from vinu_research.walk_forward import deflated_sharpe_ratio

LOG = logging.getLogger(__name__)


class ResearchService:
    def __init__(
        self,
        config: ResearchConfig | None = None,
        storage: ResearchStorage | None = None,
        strategy_store: SqliteStrategyStore | None = None,
    ) -> None:
        self._config = config or load_config()
        self._storage = storage or ResearchStorage(
            self._config.data_root / "research_meta.db"
        )
        self._owns_storage = storage is None
        self._strategy_store = strategy_store or SqliteStrategyStore(
            self._config.data_root / "strategy_store.db"
        )
        self._owns_strategy_store = strategy_store is None
        self._http = httpx.AsyncClient(timeout=5.0)

    @property
    def strategy_store(self) -> SqliteStrategyStore:
        return self._strategy_store

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
        universe: list[str] | None = None,
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
                "deflated_sharpe": 0.0,
                "holdout_passed": None,
                "stress_test_passed": None,
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
                universe=universe,
            )

            record.status = STATUS_DONE
            record.total_iterations = result.total_iterations
            record.best_iteration = result.best_iteration or -1
            if result.best_result:
                record.best_sharpe = result.best_result.metrics.sharpe_ratio
                record.best_max_dd = result.best_result.metrics.max_drawdown
                # n_trials is cumulative across every past run for this symbol
                # (queried before this run's own row is updated below, so it
                # doesn't double-count this run's iterations) plus this run's
                # own iterations — otherwise the decay-scan re-research loop
                # would reset the multiple-comparisons correction to ~n_iterations
                # every single time it re-researches the same symbol.
                prior_trials = await self._run_in_thread(
                    self._storage.cumulative_trial_count, symbol,
                )
                n_trials = prior_trials + result.total_iterations
                n_obs = max(result.best_result.equity_points - 1, 2)
                record.deflated_sharpe = deflated_sharpe_ratio(
                    sharpe=record.best_sharpe,
                    n_trials=n_trials,
                    n_obs=n_obs,
                    skew=result.best_result.metrics.skewness,
                    excess_kurtosis=result.best_result.metrics.kurtosis,
                )
            record.holdout_passed = result.holdout.passed if result.holdout else None
            record.stress_test_passed = result.stress_test.passed if result.stress_test else None
            record.report_md = result.report_md or ""
            best_rec = next(
                (r for r in result.iterations if r.iteration == result.best_iteration),
                result.iterations[-1] if result.iterations else None,
            )
            if best_rec:
                record.strategy_code = best_rec.strategy_code
            await self._run_in_thread(self._storage.update_run, record)

            response = {
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
                "deflated_sharpe": record.deflated_sharpe,
                "holdout_passed": record.holdout_passed,
                "stress_test_passed": record.stress_test_passed,
                "report_md": result.report_md,
            }
            if result.portfolio is not None:
                response["portfolio"] = {
                    "symbols": result.portfolio.symbols,
                    "avg_pairwise_correlation": result.portfolio.avg_pairwise_correlation,
                    "raw_sharpe": result.portfolio.raw_sharpe,
                    "hedged_sharpe": result.portfolio.hedged_sharpe,
                    "final_beta_estimate": result.portfolio.final_beta_estimate,
                }
            return response
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
        if result is None:
            return None
        artifact = await self._run_in_thread(self._create_artifact_from_run, result)
        response = result.to_dict()
        response["artifact_id"] = artifact.artifact_id
        return response

    def _create_artifact_from_run(self, record: ResearchRunRecord) -> Artifact:
        """Persist an approved run as a strategy artifact — the bridge between
        "a research run finished" and "a strategy is tracked over time"."""
        artifact = Artifact.create(
            type_="strategy",
            name=f"{record.symbol}_{record.id}",
            universe=[record.symbol],
        )
        artifact.status = ArtifactStatus.ACTIVE
        artifact.strategy_code = record.strategy_code
        artifact.source_run_id = record.id
        artifact.initial_sharpe = record.best_sharpe
        artifact.initial_max_dd = record.best_max_dd
        artifact.deflated_sharpe = record.deflated_sharpe
        artifact.holdout_passed = record.holdout_passed
        artifact.stress_test_passed = record.stress_test_passed
        self._strategy_store.upsert_artifact(artifact)
        self._strategy_store.append_bench_entry(BenchEntry(
            artifact_id=artifact.artifact_id,
            date=datetime.now(timezone.utc).date().isoformat(),
            sharpe=record.best_sharpe,
        ))
        return artifact

    async def has_active_strategy(self, symbol: str) -> bool:
        artifacts = await self._run_in_thread(
            self._strategy_store.list_artifacts_for_symbol,
            symbol,
            [ArtifactStatus.ACTIVE, ArtifactStatus.MONITORING],
        )
        return len(artifacts) > 0

    async def ensure_strategy(
        self,
        user_idea: str | None = None,
        symbol: str = "",
        from_date: str = "",
        to_date: str = "",
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Run research for `symbol` only if it has no ACTIVE/MONITORING strategy
        yet — the "zero strategies" trigger. Callers (a scheduler, vinu-agent)
        can call this instead of `run_research` to avoid re-researching a ticker
        that's already covered.

        When `user_idea` is None, automatically proposes a strategy idea from
        the symbol's deterministic angle context (autonomous hypothesis generation).
        """
        if not symbol:
            return {"skipped": True, "reason": "no symbol provided", "symbol": ""}
        if await self.has_active_strategy(symbol):
            return {"skipped": True, "reason": "active strategy already exists", "symbol": symbol.upper()}

        if user_idea is None:
            user_idea = await self._propose_idea(symbol)

        if not user_idea:
            return {"skipped": True, "reason": "could not propose strategy idea", "symbol": symbol.upper()}

        result = await self.run_research(user_idea, symbol, from_date, to_date, **kwargs)
        result["skipped"] = False
        return result

    async def _propose_idea(self, symbol: str) -> str | None:
        """Propose a strategy idea from angle context when no user idea is given."""
        tools = ResearchTools(self._config)
        try:
            angles = await tools.get_angle_context(symbol, self._config.interval)
        finally:
            await tools.close()

        if not angles:
            return None

        if not self._config.llm_enabled:
            tl = angles.get("trend_lifecycle", {})
            stage = tl.get("stage", "unknown")
            risk = tl.get("risk", "unknown")
            return f"Trend-following strategy for {stage} stage with {risk} risk regime"

        llm = ResearchLlmClient(self._config)
        try:
            gen = LlmStrategyGenerator(llm)
            return await gen.propose_idea_from_angles(angles)
        finally:
            await llm.close()

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
        if self._owns_strategy_store:
            await self._run_in_thread(self._strategy_store.close)
        await self._http.aclose()

    async def __aenter__(self) -> ResearchService:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()
