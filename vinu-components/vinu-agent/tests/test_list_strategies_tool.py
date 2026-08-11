from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.list_strategies_tool import ListStrategiesTool


def _tool() -> ListStrategiesTool:
    tool = ListStrategiesTool()
    tool._services_config = {"vinu_strategy": "http://vinu-strategy:8084"}
    return tool


class TestListStrategiesTool:
    def test_returns_registered_strategies(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = [
            {"name": "ma_crossover", "description": "MA crossover", "schedule": "daily", "enabled": True},
            {"name": "rsi_mean_reversion", "description": "RSI mean reversion", "schedule": "daily", "enabled": True},
        ]
        with patch("httpx.get", return_value=resp):
            result = json.loads(_tool().execute())

        assert result["status"] == "ok"
        assert result["count"] == 2
        assert {"name": "ma_crossover", "description": "MA crossover", "schedule": "daily", "enabled": True} in result["strategies"]

    def test_uses_configured_service_url(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = []
        with patch("httpx.get", return_value=resp) as mock_get:
            _tool().execute()

        mock_get.assert_called_once_with("http://vinu-strategy:8084/strategy/strategies", timeout=30)

    def test_default_url_used_when_not_configured(self) -> None:
        tool = ListStrategiesTool()  # _services_config left default {}
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = []
        with patch("httpx.get", return_value=resp) as mock_get:
            tool.execute()

        mock_get.assert_called_once_with("http://localhost:8084/strategy/strategies", timeout=30)

    def test_raises_on_http_error(self) -> None:
        resp = MagicMock()
        resp.raise_for_status.side_effect = RuntimeError("boom")
        with patch("httpx.get", return_value=resp):
            try:
                _tool().execute()
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass
