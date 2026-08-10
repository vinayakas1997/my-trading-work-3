import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.angles_tool import GetAllAnglesTool


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
