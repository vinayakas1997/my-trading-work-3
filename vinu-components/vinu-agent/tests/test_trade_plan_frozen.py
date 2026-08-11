import asyncio
import json
from unittest.mock import AsyncMock, patch

import httpx

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _client_for(handler) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://research.test")


def _force_in_process_unavailable():
    """author_trade_plan runs the real LLM-backed authoring loop -- never
    run for real in a unit test. Patched at the tool's own call site
    (same as this file's whole reason for existing: confirm the HTTP
    fallback path's contract), not vinu-research internals."""
    return patch.object(
        TradePlanTool, "_author_and_freeze_trade_plan_in_process",
        new=AsyncMock(side_effect=RuntimeError("not available")),
    )


class TestFetchFrozenTradePlanInProcess:
    def test_uses_in_process_authoring_when_available(self) -> None:
        tool = TradePlanTool()
        with patch.object(
            TradePlanTool, "_author_and_freeze_trade_plan_in_process",
            new=AsyncMock(return_value={"artifact_id": "art_inproc", "trade_plan_data": "{}"}),
        ) as mock_author:
            result = asyncio.run(tool._fetch_frozen_trade_plan(
                httpx.AsyncClient(), "http://research.test", "AAPL", "daily",
            ))
        assert result["status"] == "available"
        assert result["artifact"]["artifact_id"] == "art_inproc"
        mock_author.assert_awaited_once_with("AAPL", "daily")

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            assert request.url.path == "/research/trade-plan/AAPL"
            return httpx.Response(200, json={"artifact_id": "art_123", "trade_plan_data": "{}"})

        with _force_in_process_unavailable():
            result = asyncio.run(TestFetchFrozenTradePlan._run(tool, _client_for(handler)))
        assert result["status"] == "available"
        assert result["artifact"]["artifact_id"] == "art_123"


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

        with _force_in_process_unavailable():
            result = asyncio.run(self._run(tool, _client_for(handler)))
        assert result["status"] == "available"
        assert result["artifact"]["artifact_id"] == "art_123"

    def test_non_200_reports_unavailable(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(503)

        with _force_in_process_unavailable():
            result = asyncio.run(self._run(tool, _client_for(handler)))
        assert result["status"] == "unavailable"

    def test_connection_error_reports_error_status(self) -> None:
        tool = TradePlanTool()

        def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("connection refused", request=request)

        with _force_in_process_unavailable():
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
