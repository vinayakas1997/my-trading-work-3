"""Tests for FeaturesTool -- covers the new `preset` param, added so
idea_generator can request a named vinu-tools preset bundle (e.g.
alpha101_benchmark) instead of only ever listing indicators one by one.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.tools.features_tool import FeaturesTool


def _tool() -> FeaturesTool:
    tool = FeaturesTool()
    tool._services_config = {"vinu_tools": "http://localhost:8082"}
    return tool


class TestFeaturesToolPayload:
    def test_default_indicators_when_none_given(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "done", "id": "req1"}
        data_resp = MagicMock()
        data_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post, \
             patch("httpx.get", return_value=data_resp):
            _tool().execute(symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01")
        payload = mock_post.call_args.kwargs["json"]
        assert payload["features"] == ["sma_20", "rsi_14"]
        assert "preset" not in payload

    def test_explicit_indicators_used(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "done", "id": "req1"}
        data_resp = MagicMock()
        data_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post, \
             patch("httpx.get", return_value=data_resp):
            _tool().execute(
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
                indicators="supertrend,aroon,cmf",
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["features"] == ["supertrend", "aroon", "cmf"]

    def test_preset_sent_instead_of_features(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "done", "id": "req1"}
        data_resp = MagicMock()
        data_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post, \
             patch("httpx.get", return_value=data_resp):
            _tool().execute(
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
                preset="alpha101_benchmark",
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["preset"] == "alpha101_benchmark"
        assert "features" not in payload

    def test_error_status_returns_error_json(self) -> None:
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "failed"}
        with patch("httpx.post", return_value=mock_resp):
            result = _tool().execute(symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01")
        import json
        assert json.loads(result)["status"] == "error"
