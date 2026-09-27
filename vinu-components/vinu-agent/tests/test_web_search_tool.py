"""web_search_tool.py had zero test coverage before this file. Worth
flagging, not fixed here (a real sourcing decision, not a wiring gap):
this only calls DuckDuckGo's Instant Answer API, not real web search --
for most real-world queries `RelatedTopics` is empty, so this silently
returns `status: ok, results: []` rather than surfacing that nothing
useful was found. test_no_related_topics_is_still_a_status_ok_empty_list
below pins down that exact behavior as a regression guard, not an
endorsement of it."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.web_search_tool import WebSearchTool


def _mock_response(payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = payload
    return resp


class TestWebSearchTool:
    def test_related_topics_are_mapped_to_title_and_url(self) -> None:
        payload = {
            "RelatedTopics": [
                {"Text": "Apple Inc - Wikipedia", "FirstURL": "https://en.wikipedia.org/wiki/Apple_Inc."},
            ]
        }
        with patch("httpx.get", return_value=_mock_response(payload)):
            result = json.loads(WebSearchTool().execute(query="Apple Inc"))
        assert result["status"] == "ok"
        assert result["results"] == [
            {"title": "Apple Inc - Wikipedia", "url": "https://en.wikipedia.org/wiki/Apple_Inc."}
        ]

    def test_no_related_topics_is_still_a_status_ok_empty_list(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})):
            result = json.loads(WebSearchTool().execute(query="a very obscure query"))
        assert result["status"] == "ok"
        assert result["results"] == []

    def test_topics_without_a_text_key_are_skipped(self) -> None:
        payload = {"RelatedTopics": [{"Name": "Category group, no Text key"}]}
        with patch("httpx.get", return_value=_mock_response(payload)):
            result = json.loads(WebSearchTool().execute(query="q"))
        assert result["results"] == []

    def test_results_are_capped_at_ten(self) -> None:
        payload = {"RelatedTopics": [{"Text": f"topic {i}", "FirstURL": f"https://x/{i}"} for i in range(20)]}
        with patch("httpx.get", return_value=_mock_response(payload)):
            result = json.loads(WebSearchTool().execute(query="q"))
        assert len(result["results"]) == 10

    def test_query_param_is_forwarded(self) -> None:
        with patch("httpx.get", return_value=_mock_response({})) as mock_get:
            WebSearchTool().execute(query="AAPL earnings")
        _, kwargs = mock_get.call_args
        assert kwargs["params"]["q"] == "AAPL earnings"

    def test_request_exception_returns_error_not_a_crash(self) -> None:
        with patch("httpx.get", side_effect=RuntimeError("network down")):
            result = json.loads(WebSearchTool().execute(query="q"))
        assert result["status"] == "error"
        assert "network down" in result["error"]
