import asyncio

import httpx

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _client_for(runs_by_symbol: dict, results_by_run_id: dict | None = None) -> httpx.AsyncClient:
    results_by_run_id = results_by_run_id or {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/runs":
            symbol = request.url.params.get("symbol")
            return httpx.Response(200, json=runs_by_symbol.get(symbol, []))
        if request.url.path.startswith("/results/"):
            run_id = request.url.path.rsplit("/", 1)[-1]
            if run_id in results_by_run_id:
                return httpx.Response(200, json=results_by_run_id[run_id])
            return httpx.Response(404)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://simulator.test")


class TestFetchValidation:
    def test_matching_run_with_inline_validation(self) -> None:
        tool = TradePlanTool()
        runs_by_symbol = {
            "AAPL": [
                {
                    "run_id": "run-1",
                    "symbols": ["AAPL"],
                    "metrics": {"sharpe_ratio": 1.4},
                    "validation": {"verdict": {"passed": True, "reasons": []}},
                },
            ],
        }
        result = asyncio.run(self._run(tool, _client_for(runs_by_symbol)))
        assert result["status"] == "available"
        assert result["run_id"] == "run-1"
        assert result["validation"]["verdict"]["passed"] is True

    def test_matching_run_without_inline_validation_falls_back_to_results(self) -> None:
        tool = TradePlanTool()
        runs_by_symbol = {
            "AAPL": [
                {"run_id": "run-2", "symbols": ["AAPL"], "metrics": {}, "validation": None},
            ],
        }
        results_by_run_id = {
            "run-2": {"metrics": {"sharpe_ratio": 0.9}, "validation": {"verdict": {"passed": False}}},
        }
        result = asyncio.run(self._run(tool, _client_for(runs_by_symbol, results_by_run_id)))
        assert result["status"] == "available"
        assert result["validation"]["verdict"]["passed"] is False

    def test_no_matching_run(self) -> None:
        tool = TradePlanTool()
        result = asyncio.run(self._run(tool, _client_for({})))
        assert result["status"] == "no_matching_run"

    def test_non_200_reports_unavailable(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500)

        transport = httpx.MockTransport(handler)
        client = httpx.AsyncClient(transport=transport, base_url="http://simulator.test")
        result = asyncio.run(self._run(tool, client))
        assert result["status"] == "unavailable"

    @staticmethod
    async def _run(tool: TradePlanTool, client: httpx.AsyncClient) -> dict:
        async with client:
            return await tool._fetch_validation(client, "http://simulator.test", "AAPL")
