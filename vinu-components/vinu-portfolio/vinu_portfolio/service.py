from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

import httpx
import numpy as np
import pandas as pd

from vinu_portfolio.config import PortfolioConfig, load_config

LOG = logging.getLogger(__name__)


class PortfolioService:
    def __init__(self, config: PortfolioConfig | None = None) -> None:
        self._config = config or load_config()
        self._http = httpx.AsyncClient(timeout=10.0)

    async def close(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> PortfolioService:
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.close()

    # ------------------------------------------------------------------
    # Strategy inventory — pulls ACTIVE strategies from both mechanisms
    # ------------------------------------------------------------------

    async def list_active_strategies(self) -> list[dict[str, Any]]:
        """Unified list of all ACTIVE strategies across both mechanisms.

        Returns:
          [
            {"name": ..., "kind": "yaml"|"llm_python", "symbol": ..., "weights_source": ...},
            ...
          ]
        """
        yaml_strategies, llm_strategies = await asyncio.gather(
            self._list_yaml_strategies(),
            self._list_llm_strategies(),
            return_exceptions=True,
        )
        strategies: list[dict[str, Any]] = []
        if isinstance(yaml_strategies, list):
            strategies.extend(yaml_strategies)
        else:
            LOG.warning("Failed to list YAML strategies: %s", yaml_strategies)
        if isinstance(llm_strategies, list):
            strategies.extend(llm_strategies)
        else:
            LOG.warning("Failed to list LLM strategies: %s", llm_strategies)
        return strategies

    async def _list_yaml_strategies(self) -> list[dict[str, Any]]:
        resp = await self._http.get(f"{self._config.strategy_api_url}/strategies")
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()
        return [
            {
                "name": s.get("name", "unknown"),
                "kind": "yaml",
                "symbol": s.get("symbol", s.get("ticker", "")),
                "weights_source": f"{self._config.strategy_api_url}/weights/{s.get('name', '')}",
            }
            for s in data
        ]

    async def _list_llm_strategies(self) -> list[dict[str, Any]]:
        resp = await self._http.get(
            f"{self._config.research_api_url}/research/artifacts",
            params={"status": "ACTIVE"},
        )
        resp.raise_for_status()
        data: list[dict[str, Any]] = resp.json()
        return [
            {
                "name": a.get("name", "unknown"),
                "kind": "llm_python",
                "symbol": a.get("universe", [""])[0] if a.get("universe") else "",
                "artifact_id": a.get("artifact_id", ""),
                "weights_source": f"artifact:{a.get('artifact_id', '')}",
            }
            for a in data
        ]

    # ------------------------------------------------------------------
    # Correlation matrix across strategies
    # ------------------------------------------------------------------

    async def compute_correlation_matrix(
        self, strategies: list[dict[str, Any]]
    ) -> pd.DataFrame | None:
        """Fetch historical returns for each strategy and compute correlation."""
        returns_data: dict[str, pd.Series] = {}
        for s in strategies:
            returns = await self._fetch_strategy_returns(s)
            if returns is not None and len(returns) >= 10:
                returns_data[s["name"]] = returns

        if len(returns_data) < 2:
            LOG.info("Need at least 2 strategies with return data for correlation")
            return None

        df = pd.DataFrame(returns_data)
        return df.corr()

    async def _fetch_strategy_returns(self, strategy: dict[str, Any]) -> pd.Series | None:
        """Fetch daily returns series for a strategy."""
        try:
            if strategy["kind"] == "yaml":
                resp = await self._http.get(strategy["weights_source"])
                if resp.status_code != 200:
                    return None
                weights = resp.json()
                if isinstance(weights, list) and weights:
                    series = pd.Series(
                        [float(w.get("weight", 0)) for w in weights],
                        index=pd.to_datetime([w.get("date") for w in weights]),
                    )
                    return series.pct_change().dropna()
            elif strategy["kind"] == "llm_python":
                artifact_id = strategy.get("artifact_id", "")
                resp = await self._http.get(
                    f"{self._config.simulator_api_url}/results/{artifact_id}/equity"
                )
                if resp.status_code != 200:
                    return None
                data: list[dict] = resp.json()
                if data and len(data) >= 2:
                    series = pd.Series(
                        [float(r.get("portfolio_value", 0)) for r in data],
                        index=pd.to_datetime([r.get("date") for r in data]),
                    )
                    return series.pct_change().dropna()
        except Exception as e:
            LOG.warning("Failed to fetch returns for %s: %s", strategy.get("name"), e)
        return None

    # ------------------------------------------------------------------
    # Capital allocation — risk-parity (inverse-vol weighting)
    # ------------------------------------------------------------------

    def allocate_risk_parity(
        self,
        strategies: list[dict[str, Any]],
        returns_df: pd.DataFrame | None = None,
    ) -> list[dict[str, Any]]:
        """Inverse-volatility risk-parity allocation.

        Each strategy gets weight proportional to 1/vol. Falls back to
        equal-weight when vol data is unavailable.
        """
        if not strategies:
            return []

        weights: dict[str, float] = {}
        if returns_df is not None and len(returns_df.columns) >= 1:
            vols = returns_df.std() * np.sqrt(252)
            inv_vols = 1.0 / vols.clip(lower=1e-6)
            total = inv_vols.sum()
            if total > 0:
                raw_weights = (inv_vols / total).to_dict()
                for s in strategies:
                    w = raw_weights.get(s["name"], 1.0 / len(strategies))
                    weights[s["name"]] = min(w, self._config.max_per_strategy_weight)
            else:
                for s in strategies:
                    weights[s["name"]] = 1.0 / len(strategies)
        else:
            for s in strategies:
                weights[s["name"]] = 1.0 / len(strategies)

        total_weight = sum(weights.values())
        if total_weight > 0:
            for k in weights:
                weights[k] /= total_weight

        result = []
        for s in strategies:
            result.append({
                "name": s["name"],
                "kind": s["kind"],
                "symbol": s.get("symbol", ""),
                "target_weight": round(weights.get(s["name"], 0.0), 4),
            })
        return result

    # ------------------------------------------------------------------
    # Full portfolio construction pipeline
    # ------------------------------------------------------------------

    async def build_portfolio(self) -> dict[str, Any]:
        """Run the full portfolio construction pipeline.

        1. List active strategies (YAML + LLM)
        2. Compute correlation matrix
        3. Risk-parity allocation
        4. Apply constraints

        Returns the portfolio weights and metadata.
        """
        strategies = await self.list_active_strategies()
        if not strategies:
            return {"status": "empty", "strategies": [], "weights": [], "matrix": None}

        corr_matrix = await self.compute_correlation_matrix(strategies)

        weights = self.allocate_risk_parity(strategies, corr_matrix)

        matrix_dict: dict[str, Any] | None = None
        if corr_matrix is not None:
            matrix_dict = {
                "strategies": list(corr_matrix.columns),
                "values": corr_matrix.round(4).values.tolist(),
            }

        return {
            "status": "ok",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "n_strategies": len(strategies),
            "strategies": strategies,
            "weights": weights,
            "correlation_matrix": matrix_dict,
        }
