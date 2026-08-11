import json
from unittest.mock import AsyncMock, MagicMock, patch

from vinu_agent.tools.run_parameter_sweep_tool import RunParameterSweepTool


def _tool(services_config: dict | None = None) -> RunParameterSweepTool:
    tool = RunParameterSweepTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_research_tools",
        side_effect=RuntimeError("not available"),
    )


def _mock_grid_result():
    result = MagicMock()
    result.requested = 2
    result.succeeded = 2
    result.completeness = 1.0
    result.pbo = 0.1
    result.ranked = []
    result.outcomes = []
    return result


class TestRunParameterSweepToolInProcess:
    def test_recipe_mode_calls_real_engine_with_parsed_grid(self) -> None:
        fake_tools = MagicMock()
        fake_tools.close = AsyncMock()
        with patch("vinu_agent.broker.research_link.get_research_tools", return_value=fake_tools), patch(
            "vinu_research.sweep_grid.run_sweep_grid", new=AsyncMock(return_value=_mock_grid_result()),
        ) as mock_run:
            result = json.loads(_tool().execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover",
                param_grid='[{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}]',
            ))
        assert result["requested"] == 2
        _, kwargs = mock_run.call_args
        assert kwargs["recipe"] == "crossover"
        assert kwargs["param_grid"] == [
            {"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40},
        ]
        fake_tools.close.assert_awaited_once()

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"requested": 2}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", param_grid='[{"fast_period": 5, "slow_period": 40}]',
            )
        assert result == '{"requested": 2}'
        mock_post.assert_called_once()


class TestRunParameterSweepToolHttpFallback:
    def test_recipe_mode_uses_correct_url_and_payload(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"requested": 2}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover",
                param_grid='[{"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40}]',
            )
        args, kwargs = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/sweep/grid"
        payload = kwargs["json"]
        assert payload["recipe"] == "crossover"
        assert payload["param_grid"] == [
            {"fast_period": 5, "slow_period": 40}, {"fast_period": 10, "slow_period": 40},
        ]
        assert "base_code" not in payload
        assert result == '{"requested": 2}'

    def test_base_code_mode_payload(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                base_code="class UserStrategy: ...", param_name="fast_period",
                param_grid='[{"fast_period": 5}, {"fast_period": 10}]',
            )
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["base_code"] == "class UserStrategy: ..."
        assert payload["param_name"] == "fast_period"
        assert "recipe" not in payload

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", param_grid="[{}]",
            )
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8087/research/sweep/grid"

    def test_optional_indicators_and_capital_passed_through(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", param_grid="[{}]",
                indicators="sma_20, rsi_14", initial_capital=50000,
            )
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["indicators"] == ["sma_20", "rsi_14"]
        assert payload["initial_capital"] == 50000

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(
                    symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                    recipe="crossover", param_grid="[{}]",
                )
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass

    def test_long_timeout_for_a_whole_grid(self) -> None:
        """A grid is many real backtests in one call -- must not share the
        single-candidate tool's shorter timeout."""
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", param_grid="[{}]",
            )
        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] >= 180
