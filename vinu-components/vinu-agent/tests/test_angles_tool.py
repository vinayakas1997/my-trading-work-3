import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.angles_tool import GetAllAnglesTool, build_angle_digest, summarize_angle


def _tool(services_config: dict | None = None) -> GetAllAnglesTool:
    tool = GetAllAnglesTool()
    tool._services_config = services_config or {}
    return tool


def _mock_client(angles_list_response: dict, angle_responses: dict):
    """angles_list_response: what GET /analysis/angles returns.
    angle_responses: {angle_name: response_dict} for GET /analysis/angle/{name}/{ticker}.
    """
    def _get(url, *args, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        if url.endswith("/angles"):
            resp.json.return_value = angles_list_response
        else:
            name = url.split("/angle/")[1].split("/")[0]
            resp.json.return_value = angle_responses[name]
        return resp

    client = MagicMock()
    client.get.side_effect = _get
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


class TestGetAllAnglesTool:
    def test_angles_list_is_metadata_objects_not_flat_names(self) -> None:
        """Regression test: /analysis/angles returns a list of metadata
        objects ({name, title, purpose, path, spec}), not flat name
        strings -- the first version of this tool treated each object as
        if it were already the name string, which would have built a URL
        like /analysis/angle/{'name': 'arima', ...}/AAPL."""
        angles_list = {"angles": [
            {"name": "arima", "title": "ARIMA", "purpose": "...", "path": "...", "spec": {}},
            {"name": "trend_lifecycle", "title": "Trend Lifecycle", "purpose": "...", "path": "...", "spec": {}},
        ]}
        angle_responses = {
            "arima": {"symbol": "AAPL", "angle": "arima", "row_count": 0, "data": []},
            "trend_lifecycle": {"symbol": "AAPL", "angle": "trend_lifecycle", "row_count": 3, "data": [{"x": 1}]},
        }
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL"))

        assert result["angle_count"] == 2
        assert result["angles_with_data"] == 1
        assert result["angles"]["arima"]["row_count"] == 0
        assert result["angles"]["trend_lifecycle"]["row_count"] == 3

    def test_ticker_is_uppercased(self) -> None:
        angles_list = {"angles": [{"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"arima": {"symbol": "AAPL", "angle": "arima", "row_count": 0, "data": []}}
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="aapl"))

        assert result["ticker"] == "AAPL"

    def test_angle_fetch_failure_is_reported_not_raised(self) -> None:
        angles_list = {"angles": [
            {"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}},
            {"name": "broken_angle", "title": "", "purpose": "", "path": "", "spec": {}},
        ]}

        def _get(url, *args, **kwargs):
            resp = MagicMock()
            if url.endswith("/angles"):
                resp.raise_for_status = MagicMock()
                resp.json.return_value = angles_list
                return resp
            if "broken_angle" in url:
                raise RuntimeError("connection refused")
            resp.raise_for_status = MagicMock()
            resp.json.return_value = {"symbol": "AAPL", "angle": "arima", "row_count": 0, "data": []}
            return resp

        client = MagicMock()
        client.get.side_effect = _get
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        tool = _tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL"))

        assert result["angle_count"] == 2
        assert result["angles"]["broken_angle"]["row_count"] == 0
        assert "connection refused" in result["angles"]["broken_angle"]["error"]

    def test_uses_configured_service_url(self) -> None:
        angles_list = {"angles": []}
        client = _mock_client(angles_list, {})
        tool = _tool({"vinu_initial_analysis": "http://custom-host:9999"})

        with patch("httpx.Client", return_value=client):
            tool.execute(ticker="AAPL")

        called_url = client.get.call_args_list[0].args[0]
        assert called_url == "http://custom-host:9999/analysis/angles"


class TestSummarizeAngle:
    """Regression for the '2 of 28 angles' gate-conflict: GetAllAnglesTool
    already fetches every angle, but nothing ever turned that into a
    structured digest for forecast_skill's prompt -- see
    high-expectations gate-conflict audit."""

    def test_normal_row_is_digested(self) -> None:
        result = {"row_count": 2, "data": [{"stage": "early"}, {"stage": "mature", "score": 0.7}]}
        digest = summarize_angle("trend_lifecycle", result)
        assert digest == {"stage": "mature", "score": 0.7}

    def test_empty_or_error_entry_returns_none(self) -> None:
        assert summarize_angle("arima", {"row_count": 0, "data": []}) is None
        assert summarize_angle("broken", {"row_count": 0, "error": "boom", "data": []}) is None

    def test_oversized_string_field_is_dropped_not_truncated(self) -> None:
        result = {"row_count": 1, "data": [{"note": "x" * 500, "score": 1.0}]}
        digest = summarize_angle("angle", result)
        assert digest == {"score": 1.0}

    def test_field_count_is_not_capped(self) -> None:
        """No per-angle field cap: an early cutoff risked dropping an
        angle's actual signal fields behind whatever happened to come
        first in the raw row (e.g. symbol/timestamp/id ahead of the
        metrics that matter)."""
        row = {f"f{i}": i for i in range(10)}
        result = {"row_count": 1, "data": [row]}
        digest = summarize_angle("angle", result)
        assert digest == row

    def test_malformed_row_fails_open_to_none(self) -> None:
        assert summarize_angle("angle", {"row_count": 1, "data": ["not-a-dict"]}) is None
        assert summarize_angle("angle", "not-a-dict") is None


class TestBuildAngleDigest:
    def test_mixed_angles_only_keeps_ones_with_data(self) -> None:
        angles_data = {
            "angles": {
                "arima": {"row_count": 0, "data": []},
                "trend_lifecycle": {"row_count": 1, "data": [{"stage": "early"}]},
                "regime_analysis": {"row_count": 1, "data": [{"regime": "bull"}]},
            }
        }
        digest = build_angle_digest(angles_data)
        assert set(digest.keys()) == {"trend_lifecycle", "regime_analysis"}
        assert digest["trend_lifecycle"] == {"stage": "early"}

    def test_angle_count_is_capped(self) -> None:
        angles_data = {
            "angles": {
                f"angle_{i}": {"row_count": 1, "data": [{"v": i}]} for i in range(40)
            }
        }
        digest = build_angle_digest(angles_data)
        assert len(digest) == 30

    def test_malformed_angles_data_fails_open_to_empty(self) -> None:
        assert build_angle_digest({}) == {}
        assert build_angle_digest({"angles": "not-a-dict"}) == {}
