"""Step 9: get_reflection_synthesis is the first real consumer of
vinu-reflection's maturity-synthesis brain -- HTTP only (no in-process
option; vinu-reflection already depends on vinu-agent, so a reverse
import would be circular)."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.reflection_synthesis_tool import GetReflectionSynthesisTool


def _tool() -> GetReflectionSynthesisTool:
    tool = GetReflectionSynthesisTool()
    tool._services_config = {"vinu_reflection": "http://reflection-api:8092"}
    return tool


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload
    return resp


class TestGetReflectionSynthesisTool:
    def test_no_synthesis_yet_is_reported_not_treated_as_an_error(self) -> None:
        with patch("httpx.get", return_value=_mock_response({"status": "none"})) as mock_get:
            result = json.loads(_tool().execute())
        assert result == {"status": "none"}
        args, _ = mock_get.call_args
        assert args[0] == "http://reflection-api:8092/reflection/synthesis/latest"

    def test_real_synthesis_is_returned_as_is(self) -> None:
        payload = {
            "status": "ok",
            "synthesis": {
                "synthesis_id": "syn_1", "proposed_action_type": "narrative_only",
            },
        }
        with patch("httpx.get", return_value=_mock_response(payload)):
            result = json.loads(_tool().execute())
        assert result == payload

    def test_request_failure_is_caught_and_reported(self) -> None:
        with patch("httpx.get", side_effect=Exception("connection refused")):
            result = json.loads(_tool().execute())
        assert result["status"] == "error"
        assert "connection refused" in result["error"]

    def test_default_url_used_when_not_configured(self) -> None:
        tool = GetReflectionSynthesisTool()
        with patch("httpx.get", return_value=_mock_response({"status": "none"})) as mock_get:
            tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8092/reflection/synthesis/latest"
