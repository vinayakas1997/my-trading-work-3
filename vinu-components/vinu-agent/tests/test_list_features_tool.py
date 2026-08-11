"""Tests for ListAvailableFeaturesTool -- closes a real gap found via a
real-LLM test run: idea_generator only ever requested sma_20/sma_50/rsi_14
across every real call, because nothing exposed vinu-tools' real 24-item
catalog / 11 presets, so it could only guess from its tool description's
3 examples. See New-talk-agents/new-thinking/agentic-e2e-twst-files-and-status/
01-findings-and-status.md.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.list_features_tool import ListAvailableFeaturesTool


def _tool() -> ListAvailableFeaturesTool:
    tool = ListAvailableFeaturesTool()
    tool._services_config = {"vinu_tools": "http://localhost:8082"}
    return tool


class TestListAvailableFeaturesTool:
    def test_combines_catalog_and_presets(self) -> None:
        catalog_resp = MagicMock()
        catalog_resp.json.return_value = {"data": [
            {"kind": "sma", "description": "Simple moving average", "examples": ["sma_20"]},
            {"kind": "supertrend", "description": "Supertrend (ATR-based)", "examples": ["supertrend"]},
        ]}
        presets_resp = MagicMock()
        presets_resp.json.return_value = {"data": [
            {"name": "basic_ta", "description": "Minimal trend and momentum", "features": ["sma_20", "rsi_14", "daily_return"]},
            {"name": "alpha101_benchmark", "description": "WorldQuant 101 alphas", "features": [f"ALPHA101_{i:03d}" for i in range(101)]},
        ]}
        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.side_effect = [catalog_resp, presets_resp]

        with patch("httpx.Client", return_value=mock_client):
            result = json.loads(_tool().execute())

        assert [i["kind"] for i in result["indicators"]] == ["sma", "supertrend"]
        assert result["presets"][0] == {"name": "basic_ta", "description": "Minimal trend and momentum", "feature_count": 3}
        assert result["presets"][1]["feature_count"] == 101

    def test_preset_feature_lists_are_not_expanded_inline(self) -> None:
        """alpha360 alone is 360 entries -- the tool must report counts, not
        the full feature lists, or a single call could dominate context."""
        catalog_resp = MagicMock()
        catalog_resp.json.return_value = {"data": []}
        presets_resp = MagicMock()
        presets_resp.json.return_value = {"data": [
            {"name": "alpha360", "description": "", "features": [f"F{i}" for i in range(360)]},
        ]}
        mock_client = MagicMock()
        mock_client.__enter__.return_value.get.side_effect = [catalog_resp, presets_resp]

        with patch("httpx.Client", return_value=mock_client):
            result = json.loads(_tool().execute())

        assert "features" not in result["presets"][0]
        assert result["presets"][0]["feature_count"] == 360
