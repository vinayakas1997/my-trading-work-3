import asyncio
import json

import httpx

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _client_for(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://research.test")


class TestFetchFrozenTradePlan:
    def test_available_trade_plan(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/research/trade-plan/AAPL"
            assert json.loads(request.content) == {"timeframe": "daily"}
            return httpx.Response(200, json={
                "artifact_id": "art_123",
                "type": "trade_plan",
                "status": "CREATED",
                "trade_plan_data": "{\"symbol\": \"AAPL\"}",
            })

        result = asyncio.run(self._run(tool, _client_for(handler)))
        assert result["status"] == "available"
        assert result["artifact"]["artifact_id"] == "art_123"

    def test_non_200_reports_unavailable(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        result = asyncio.run(self._run(tool, _client_for(handler)))
        assert result["status"] == "unavailable"

    def test_connection_error_reports_error_status(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        result = asyncio.run(self._run(tool, _client_for(handler)))
        assert result["status"] == "error"

    @staticmethod
    async def _run(tool: TradePlanTool, client: httpx.AsyncClient) -> dict:
        async with client:
            return await tool._fetch_frozen_trade_plan(client, "http://research.test", "AAPL", "daily")


class TestRenderFrozenPlanBlock:
    def test_renders_artifact_as_json_block(self) -> None:
        tool = TradePlanTool()
        block = tool._render_frozen_plan_block({"artifact": {"artifact_id": "art_123"}})
        assert "<!-- frozen_trade_plan -->" in block
        assert "art_123" in block
        assert "<!-- /frozen_trade_plan -->" in block
