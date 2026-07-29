from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

import httpx

LOG = logging.getLogger(__name__)


class ShadowEvaluator:
    """Automated shadow-account comparison: compares paper-trading P&L against
    backtest expectations and promotes BENCHING strategies to ACTIVE when the
    paper performance is within tolerance.

    This closes the gap between "a strategy was approved in research" and
    "it's trusted with real capital" — the paper-trading phase becomes an
    automated gate, not a manual review step.
    """

    def __init__(
        self,
        research_api_url: str = "http://127.0.0.1:8087",
        agent_api_url: str = "http://127.0.0.1:8086",
        max_sharpe_degradation: float = 0.5,
        min_paper_days: int = 5,
    ) -> None:
        self._research_api = research_api_url
        self._agent_api = agent_api_url
        self._max_sharpe_degradation = max_sharpe_degradation
        self._min_paper_days = min_paper_days
        self._http = httpx.AsyncClient(timeout=15.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def evaluate_all(self) -> list[dict[str, Any]]:
        """Evaluate all BENCHING artifacts and promote qualifying ones."""
        results: list[dict[str, Any]] = []
        artifacts = await self._list_benching_artifacts()

        for art in artifacts:
            result = await self._evaluate_one(art)
            results.append(result)

        return results

    async def _list_benching_artifacts(self) -> list[dict[str, Any]]:
        try:
            resp = await self._http.get(
                f"{self._research_api}/artifacts",
                params={"status": "BENCHING"},
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            LOG.warning("Failed to list benching artifacts: %s", e)
        return []

    async def _evaluate_one(self, artifact: dict[str, Any]) -> dict[str, Any]:
        artifact_id = artifact.get("artifact_id", "unknown")
        name = artifact.get("name", "unknown")
        backtest_sharpe = artifact.get("initial_sharpe", 0.0)

        paper_sharpe = await self._fetch_paper_sharpe(artifact_id)

        if paper_sharpe is None:
            return {
                "artifact_id": artifact_id,
                "name": name,
                "status": "insufficient_data",
                "paper_sharpe": None,
                "backtest_sharpe": backtest_sharpe,
                "promoted": False,
            }

        degradation = (
            (backtest_sharpe - paper_sharpe) / max(abs(backtest_sharpe), 1e-6)
            if backtest_sharpe != 0 else 1.0
        )

        promoted = paper_sharpe > 0 and degradation <= self._max_sharpe_degradation

        if promoted:
            await self._promote_artifact(artifact_id)

        return {
            "artifact_id": artifact_id,
            "name": name,
            "status": "promoted" if promoted else "below_threshold",
            "paper_sharpe": round(paper_sharpe, 4),
            "backtest_sharpe": round(backtest_sharpe, 4),
            "degradation": round(degradation, 4),
            "promoted": promoted,
        }

    async def _fetch_paper_sharpe(self, artifact_id: str) -> float | None:
        """Fetch paper-trading P&L for an artifact and compute Sharpe."""
        try:
            resp = await self._http.get(
                f"{self._agent_api}/broker/performance/{artifact_id}",
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            returns = data.get("daily_returns", [])
            if len(returns) < self._min_paper_days:
                return None
            import numpy as np
            arr = np.array(returns, dtype=float)
            if arr.std(ddof=1) == 0:
                return 0.0
            sharpe = (arr.mean() / arr.std(ddof=1)) * np.sqrt(252)
            return float(sharpe)
        except Exception as e:
            LOG.debug("Could not fetch paper Sharpe for %s: %s", artifact_id, e)
        return None

    async def _promote_artifact(self, artifact_id: str) -> None:
        """Transition artifact from BENCHING to ACTIVE via research API."""
        try:
            resp = await self._http.post(
                f"{self._research_api}/artifacts/{artifact_id}/promote",
            )
            if resp.status_code == 200:
                LOG.info("Promoted artifact %s to ACTIVE", artifact_id)
            else:
                LOG.warning("Failed to promote %s: HTTP %d", artifact_id, resp.status_code)
        except Exception as e:
            LOG.warning("Failed to promote %s: %s", artifact_id, e)
