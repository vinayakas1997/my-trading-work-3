from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.tools.strategy_tool import StrategyTool


def _tool() -> StrategyTool:
    tool = StrategyTool()
    tool._services_config = {"vinu_strategy": "http://vinu-strategy:8084"}
    return tool


class TestStrategyTool:
    def test_calls_the_real_mounted_path(self) -> None:
        """Regression test: run_strategy previously called {url}/strategies/...
        with no /strategy prefix, 404ing against every real deployment --
        vinu-strategy has always mounted its routes under /strategy (both
        standalone and inside the merged quant-core-api container)."""
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.text = '{"status": "ok"}'
        with patch("httpx.post", return_value=resp) as mock_post:
            _tool().execute(strategy_name="ma_crossover", symbol="AAPL")

        args, kwargs = mock_post.call_args
        assert args[0] == "http://vinu-strategy:8084/strategy/strategies/ma_crossover/evaluate"
        assert kwargs["params"] == {"symbols": "AAPL"}

    def test_default_url_used_when_not_configured(self) -> None:
        tool = StrategyTool()  # _services_config left default {}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.text = "{}"
        with patch("httpx.post", return_value=resp) as mock_post:
            tool.execute(strategy_name="ma_crossover", symbol="AAPL")

        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8084/strategy/strategies/ma_crossover/evaluate"
