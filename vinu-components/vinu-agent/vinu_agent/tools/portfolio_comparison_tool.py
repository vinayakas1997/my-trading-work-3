"""Agent tool comparing live/paper positions against backtest expectations."""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

from ..agent.tools import BaseTool

logger = logging.getLogger(__name__)


class PortfolioComparisonTool(BaseTool):
    name = "compare_portfolio"
    description = "Compare current live/paper positions and P&L against each strategy's backtest expectations"
    parameters = {
        "format": {
            "type": "string",
            "description": "Output format: 'text' for human-readable, 'json' for raw data",
            "enum": ["text", "json"],
        },
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    async def execute_async(self, format: str = "text") -> str:
        portfolio_api = self._services_config.get("vinu_portfolio", "http://localhost:8090")
        research_api = self._services_config.get("vinu_research", "http://localhost:8087")

        async with httpx.AsyncClient(timeout=15.0) as client:
            portfolio_data = await self._fetch_portfolio(client, portfolio_api)
            artifacts = await self._fetch_artifacts(client, research_api)

        if format == "json":
            return json.dumps({
                "portfolio": portfolio_data,
                "artifacts": artifacts,
            }, indent=2, default=str)

        return self._format_text(portfolio_data, artifacts)

    async def _fetch_portfolio(self, client: httpx.AsyncClient, url: str) -> dict[str, Any]:
        try:
            resp = await client.get(f"{url}/portfolio")
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch portfolio: %s", e)
        return {"status": "unavailable"}

    async def _fetch_artifacts(self, client: httpx.AsyncClient, url: str) -> list[dict[str, Any]]:
        try:
            resp = await client.get(
                f"{url}/research/artifacts",
                params={"status": "ACTIVE,MONITORING,BENCHING"},
            )
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.warning("Failed to fetch artifacts: %s", e)
        return []

    def _format_text(self, portfolio: dict[str, Any], artifacts: list[dict[str, Any]]) -> str:
        lines = ["## Portfolio Comparison", ""]

        if portfolio.get("status") == "ok":
            lines.append(f"**Active Strategies:** {portfolio.get('n_strategies', 0)}")
            lines.append(f"**Target Weights:**")
            for w in portfolio.get("weights", []):
                lines.append(f"  - {w.get('name')} ({w.get('symbol')}): {w.get('target_weight', 0)*100:.1f}%")
            lines.append("")
        else:
            lines.append("Portfolio service unavailable.")
            lines.append("")

        lines.append("### Strategy Artifacts")
        lines.append("")
        lines.append(f"{'Name':<30} {'Status':<15} {'Init Sharpe':<12} {'Symbol':<10}")
        lines.append("-" * 70)
        for a in artifacts:
            name = (a.get("name") or "?")[:28]
            status = a.get("status", "?")
            sharpe = a.get("initial_sharpe", 0)
            symbol = (a.get("universe") or ["?"])[0]
            lines.append(f"{name:<30} {status:<15} {sharpe:<12.2f} {symbol:<10}")

        lines.append("")
        lines.append("*Run `compare_portfolio` again to refresh.*")

        return "\n".join(lines)

    def execute(self, **kwargs) -> str:
        import asyncio
        return asyncio.run(self.execute_async(**kwargs))
