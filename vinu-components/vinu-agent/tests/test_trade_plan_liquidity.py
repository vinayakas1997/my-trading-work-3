import asyncio

import httpx
import pytest

from vinu_agent.tools.trade_plan_tool import TradePlanTool


def _bars(volumes: list[float], closes: list[float]) -> list[dict]:
    return [
        {"bar_ts": i, "open": c, "high": c, "low": c, "close": c, "volume": v}
        for i, (v, c) in enumerate(zip(volumes, closes))
    ]


def _client_for(data: list[dict], status_code: int = 200) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code, json={"data": data})

    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, base_url="http://stock-price.test")


class TestFetchLiquidityCheck:
    def test_normal_volume_and_volatility_is_met(self) -> None:
        tool = TradePlanTool()
        volumes = [1000.0] * 19 + [1000.0]
        closes = [100.0 + (i % 2) * 0.1 for i in range(20)]
        client = asyncio.run(self._run(tool, _client_for(_bars(volumes, closes))))
        assert client["status"] == "available"
        assert client["normal"] is True

    def test_volume_dry_up_flags_caution(self) -> None:
        tool = TradePlanTool()
        volumes = [1000.0] * 19 + [50.0]
        closes = [100.0 + (i % 2) * 0.1 for i in range(20)]
        result = asyncio.run(self._run(tool, _client_for(_bars(volumes, closes))))
        assert result["status"] == "available"
        assert result["normal"] is False
        assert result["volume_ratio"] < 0.3

    def test_volatility_spike_flags_caution(self) -> None:
        tool = TradePlanTool()
        closes = [100.0 + (i % 2) * 0.01 for i in range(99)] + [150.0]
        volumes = [1000.0] * len(closes)
        result = asyncio.run(self._run(tool, _client_for(_bars(volumes, closes))))
        assert result["status"] == "available"
        assert result["normal"] is False

    def test_insufficient_bars_reports_status(self) -> None:
        tool = TradePlanTool()
        result = asyncio.run(self._run(tool, _client_for(_bars([1.0, 2.0], [100.0, 101.0]))))
        assert result["status"] == "insufficient_data"

    def test_non_200_reports_unavailable(self) -> None:
        tool = TradePlanTool()
        result = asyncio.run(self._run(tool, _client_for([], status_code=500)))
        assert result["status"] == "unavailable"

    @staticmethod
    async def _run(tool: TradePlanTool, client: httpx.AsyncClient) -> dict:
        async with client:
            return await tool._fetch_liquidity_check(client, "http://stock-price.test", "AAPL", "1d")
