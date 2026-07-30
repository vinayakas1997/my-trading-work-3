import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.run_sweep_candidate_tool import ListSweepRecipesTool, RunSweepCandidateTool


def _tool(services_config: dict | None = None) -> RunSweepCandidateTool:
    tool = RunSweepCandidateTool()
    tool._services_config = services_config or {}
    return tool


class TestRunSweepCandidateTool:
    def test_recipe_mode_uses_correct_url_and_payload(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": "abc"}'
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", params='{"fast_period": 9, "slow_period": 40}',
            )
        args, kwargs = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/sweep/candidate"
        payload = kwargs["json"]
        assert payload["recipe"] == "crossover"
        assert payload["params"] == {"fast_period": 9, "slow_period": 40}
        assert "base_code" not in payload
        assert result == '{"run_id": "abc"}'

    def test_base_code_mode_payload(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                base_code="class UserStrategy: ...", param_name="fast_period", param_value=9,
            )
        _, kwargs = mock_post.call_args
        payload = kwargs["json"]
        assert payload["base_code"] == "class UserStrategy: ..."
        assert payload["param_name"] == "fast_period"
        assert payload["param_value"] == 9
        assert "recipe" not in payload

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31", recipe="crossover", params="{}")
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8087/research/sweep/candidate"

    def test_optional_indicators_and_capital_passed_through(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", params="{}",
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
        with patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31", recipe="crossover", params="{}")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass


def _recipes_tool(services_config: dict | None = None) -> ListSweepRecipesTool:
    tool = ListSweepRecipesTool()
    tool._services_config = services_config or {}
    return tool


class TestListSweepRecipesTool:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _recipes_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"recipes": []}'
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/sweep/recipes"
        assert result == '{"recipes": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _recipes_tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/sweep/recipes"
