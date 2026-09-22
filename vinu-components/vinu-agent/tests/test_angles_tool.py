import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.angles_tool import (
    GetAllAnglesTool,
    GetClusterAnglesTool,
    build_angle_digest,
    summarize_angle,
)


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

    def test_time_format_defaults_to_1D_when_omitted(self) -> None:
        """Backward compatibility: a caller that never passes time_format
        must see identical behavior to before this parameter existed."""
        angles_list = {"angles": [{"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"arima": {"symbol": "AAPL", "angle": "arima", "row_count": 0, "data": []}}
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL"))

        assert result["time_format"] == "1D"
        # The fallback GET must carry granularity=1D as a query param, not
        # silently drop back to AngleStorage.read()'s own bare default.
        fallback_call = next(c for c in client.get.call_args_list if "/angle/arima/" in c.args[0])
        assert fallback_call.kwargs.get("params") == {"granularity": "1D"}

    def test_time_format_is_threaded_through_to_fallback_call(self) -> None:
        angles_list = {"angles": [{"name": "garch", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"garch": {"symbol": "AAPL", "angle": "garch", "row_count": 1, "data": [{"vol": 0.2}]}}
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", time_format="1H"))

        assert result["time_format"] == "1H"
        fallback_call = next(c for c in client.get.call_args_list if "/angle/garch/" in c.args[0])
        assert fallback_call.kwargs.get("params") == {"granularity": "1H"}

    def test_time_format_with_no_v1_url_segment_skips_v1_and_uses_fallback(self) -> None:
        """1W/1M/6M (real time_formats a couple of angles declare, e.g.
        backtesting_44_metrics/regime_analysis) have no v1 fetch route
        segment at all -- must go straight to the fallback route, not
        attempt (and coincidentally-or-not fail into) the v1 path."""
        angles_list = {"angles": [{"name": "regime_analysis", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {
            "regime_analysis": {"symbol": "AAPL", "angle": "regime_analysis", "row_count": 1, "data": [{"regime": "bull"}]},
        }
        v1_calls: list[str] = []

        def _get(url, *args, **kwargs):
            resp = MagicMock()
            resp.raise_for_status = MagicMock()
            if url.endswith("/angles"):
                resp.json.return_value = angles_list
            elif "/fetch/" in url:
                v1_calls.append(url)
                resp.status_code = 404
                resp.json.return_value = {}
            else:
                name = url.split("/angle/")[1].split("/")[0]
                resp.json.return_value = angle_responses[name]
            return resp

        client = MagicMock()
        client.get.side_effect = _get
        client.__enter__.return_value = client
        client.__exit__.return_value = False
        tool = _tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", time_format="1M"))

        assert not v1_calls  # v1 was never attempted for an unsupported granularity
        assert result["angles"]["regime_analysis"]["row_count"] == 1

    def test_repeat_call_same_ticker_and_time_format_is_cached(self) -> None:
        """Real fix, found live 2026-09-22: cross_cluster_analyst's own
        prompt already says 'call get_all_angles once', but the model
        called it 15 times in one real run anyway (same lesson as the
        prompt-injection fix: an instruction alone doesn't reliably hold
        against this local model). A repeat call for the same
        (ticker, time_format) must hit the network exactly once."""
        angles_list = {"angles": [{"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"arima": {"symbol": "AAPL", "angle": "arima", "row_count": 1, "data": [{"x": 1}]}}
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client) as mock_client_cls:
            first = tool.execute(ticker="AAPL")
            second = tool.execute(ticker="AAPL")

        assert first == second
        # httpx.Client() itself (the "with httpx.Client(...) as client" line)
        # was only ever constructed once -- the second call never opened a
        # new connection at all, let alone re-fetched all 28 angles.
        assert mock_client_cls.call_count == 1

    def test_different_ticker_is_not_cached_together(self) -> None:
        angles_list = {"angles": [{"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"arima": {"symbol": "AAPL", "angle": "arima", "row_count": 1, "data": [{"x": 1}]}}
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client) as mock_client_cls:
            tool.execute(ticker="AAPL")
            tool.execute(ticker="MSFT")

        assert mock_client_cls.call_count == 2

    def test_different_time_format_is_not_cached_together(self) -> None:
        angles_list = {"angles": [{"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"arima": {"symbol": "AAPL", "angle": "arima", "row_count": 1, "data": [{"x": 1}]}}
        client = _mock_client(angles_list, angle_responses)
        tool = _tool()

        with patch("httpx.Client", return_value=client) as mock_client_cls:
            tool.execute(ticker="AAPL", time_format="1D")
            tool.execute(ticker="AAPL", time_format="1H")

        assert mock_client_cls.call_count == 2

    def test_cache_is_per_instance_not_shared_across_tools(self) -> None:
        """build_registry() constructs a fresh GetAllAnglesTool per
        ticker-run (scheduler_workers.py::run_team_for_ticker) -- confirm
        a new instance never sees another instance's cached result."""
        angles_list = {"angles": [{"name": "arima", "title": "", "purpose": "", "path": "", "spec": {}}]}
        angle_responses = {"arima": {"symbol": "AAPL", "angle": "arima", "row_count": 1, "data": [{"x": 1}]}}
        client = _mock_client(angles_list, angle_responses)

        with patch("httpx.Client", return_value=client) as mock_client_cls:
            _tool().execute(ticker="AAPL")
            _tool().execute(ticker="AAPL")

        assert mock_client_cls.call_count == 2


def _cluster_tool(services_config: dict | None = None) -> GetClusterAnglesTool:
    tool = GetClusterAnglesTool()
    tool._services_config = services_config or {}
    return tool


def _mock_fallback_only_client(angle_responses: dict):
    """No /angles list call for GetClusterAnglesTool -- it fetches its
    cluster's real member list directly, never the full 28-angle list."""
    def _get(url, *args, **kwargs):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        name = url.split("/angle/")[1].split("/")[0]
        resp.json.return_value = angle_responses[name]
        return resp

    client = MagicMock()
    client.get.side_effect = _get
    client.__enter__.return_value = client
    client.__exit__.return_value = False
    return client


class TestGetClusterAnglesTool:
    def test_unknown_cluster_is_reported_not_raised(self) -> None:
        tool = _cluster_tool()
        result = json.loads(tool.execute(ticker="AAPL", cluster="Z"))
        assert result["status"] == "error"
        assert "Z" in result["error"]

    def test_only_fetches_the_named_clusters_real_members(self) -> None:
        """Structural isolation check: Cluster C has exactly 2 real
        members (garch, drawdown_deep_dive) -- this must never fetch or
        return any angle outside that list, e.g. kalman_filters (a real
        Cluster A member)."""
        angle_responses = {
            "garch": {"symbol": "AAPL", "angle": "garch", "row_count": 1, "data": [{"forecast_volatility": 0.02}]},
            "drawdown_deep_dive": {"symbol": "AAPL", "angle": "drawdown_deep_dive", "row_count": 1, "data": [{"current_drawdown_pct": -0.03}]},
        }
        client = _mock_fallback_only_client(angle_responses)
        tool = _cluster_tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", cluster="C"))

        assert result["cluster"] == "C"
        assert set(result["cluster_members"]) == {"garch", "drawdown_deep_dive"}
        assert set(result["angles"].keys()) == {"garch", "drawdown_deep_dive"}
        assert "kalman_filters" not in result["angles"]
        assert result["angle_count"] == 2
        assert result["angles_with_data"] == 2

    def test_lowercase_cluster_letter_is_normalized(self) -> None:
        angle_responses = {
            "garch": {"symbol": "AAPL", "angle": "garch", "row_count": 0, "data": []},
            "drawdown_deep_dive": {"symbol": "AAPL", "angle": "drawdown_deep_dive", "row_count": 0, "data": []},
        }
        client = _mock_fallback_only_client(angle_responses)
        tool = _cluster_tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", cluster="c"))

        assert result["cluster"] == "C"

    def test_angles_with_data_only_counts_real_rows(self) -> None:
        angle_responses = {
            "garch": {"symbol": "AAPL", "angle": "garch", "row_count": 1, "data": [{"forecast_volatility": 0.02}]},
            "drawdown_deep_dive": {"symbol": "AAPL", "angle": "drawdown_deep_dive", "row_count": 0, "data": []},
        }
        client = _mock_fallback_only_client(angle_responses)
        tool = _cluster_tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", cluster="C"))

        assert result["angles_with_data"] == 1

    def test_time_format_defaults_to_1D(self) -> None:
        angle_responses = {
            "garch": {"symbol": "AAPL", "angle": "garch", "row_count": 0, "data": []},
            "drawdown_deep_dive": {"symbol": "AAPL", "angle": "drawdown_deep_dive", "row_count": 0, "data": []},
        }
        client = _mock_fallback_only_client(angle_responses)
        tool = _cluster_tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", cluster="C"))

        assert result["time_format"] == "1D"

    def test_cluster_b_has_all_14_real_members(self) -> None:
        angle_responses = {
            name: {"symbol": "AAPL", "angle": name, "row_count": 0, "data": []}
            for name in [
                "chronos", "dlinear", "itransformer", "kronos", "lag_llama",
                "lpatchtst", "lstm", "moirai", "moment", "patchtst", "tft",
                "timer_timerxl", "timesfm", "tips_regime_aware_transformer",
            ]
        }
        client = _mock_fallback_only_client(angle_responses)
        tool = _cluster_tool()

        with patch("httpx.Client", return_value=client):
            result = json.loads(tool.execute(ticker="AAPL", cluster="B"))

        assert result["angle_count"] == 14
        assert len(result["cluster_members"]) == 14


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
