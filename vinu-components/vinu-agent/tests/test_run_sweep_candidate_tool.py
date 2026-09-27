import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vinu_agent.tools.run_sweep_candidate_tool import ListSweepRecipesTool, RunSweepCandidateTool


def _tool(services_config: dict | None = None) -> RunSweepCandidateTool:
    tool = RunSweepCandidateTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    """item #17 finding #3: research_link.py's own module docstring
    documents ImportError specifically as the one legitimate reason the
    in-process path falls back to HTTP (vinu-research not installed in
    this deployment) -- so that's what these tests simulate, not a
    generic RuntimeError standing in for "anything went wrong"."""
    return patch(
        "vinu_agent.broker.research_link.get_research_tools",
        side_effect=ImportError("vinu_research not installed"),
    )


def _mock_sweep_result(**overrides):
    result = MagicMock()
    result.run_id = overrides.get("run_id", "abc")
    result.strategy_name = overrides.get("strategy_name", "crossover")
    result.strategy_code = overrides.get("strategy_code", "class UserStrategy: ...")
    result.params_used = overrides.get("params_used", {"fast_period": 9})
    result.metrics = overrides.get("metrics", {"sharpe_ratio": 1.1})
    result.trade_count = overrides.get("trade_count", 12)
    result.validation = overrides.get("validation", {})
    return result


class TestRunSweepCandidateToolInProcess:
    def test_recipe_mode_calls_real_engine_with_parsed_params(self) -> None:
        fake_tools = MagicMock()
        fake_tools.close = AsyncMock()
        with patch("vinu_agent.broker.research_link.get_research_tools", return_value=fake_tools), patch(
            "vinu_research.sweep.run_sweep_candidate", new=AsyncMock(return_value=_mock_sweep_result()),
        ) as mock_run:
            result = json.loads(_tool().execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", params='{"fast_period": 9, "slow_period": 40}',
            ))
        assert result["run_id"] == "abc"
        assert result["strategy_code"] == "class UserStrategy: ..."
        _, kwargs = mock_run.call_args
        assert kwargs["recipe"] == "crossover"
        assert kwargs["params"] == {"fast_period": 9, "slow_period": 40}
        assert kwargs["tools"] is fake_tools
        fake_tools.close.assert_awaited_once()

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": "abc"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            result = tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", params='{"fast_period": 9, "slow_period": 40}',
            )
        assert result == '{"run_id": "abc"}'
        args, kwargs = mock_post.call_args
        assert args[0] == "http://research-api:8087/research/sweep/candidate"
        assert kwargs["json"]["recipe"] == "crossover"

    def test_http_fallback_timeout_exceeds_the_simulator_clients_own_worst_case_retry_budget(self) -> None:
        """item #17 finding #4: the old hardcoded 180s here was less than
        vinu-research's own simulator client worst case (3 attempts *
        120s timeout + backoff, ~365s) -- a legitimately slow-but-alive
        call could exceed 180s and get read as a failure. Regression
        guard on the actual number, not just that some timeout is passed."""
        from vinu_agent.tools.run_sweep_candidate_tool import (
            _SIMULATOR_WORST_CASE_SEC,
            _SWEEP_CANDIDATE_TIMEOUT_SEC,
        )

        assert _SIMULATOR_WORST_CASE_SEC == pytest.approx(365.0)
        assert _SWEEP_CANDIDATE_TIMEOUT_SEC > _SIMULATOR_WORST_CASE_SEC

        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": "abc"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(
                symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                recipe="crossover", params='{"fast_period": 9, "slow_period": 40}',
            )
        _, kwargs = mock_post.call_args
        assert kwargs["timeout"] == _SWEEP_CANDIDATE_TIMEOUT_SEC

    def test_a_real_infrastructure_error_propagates_instead_of_retrying_over_http(self) -> None:
        """item #17 finding #3 + the compound retry-storm risk (finding #4):
        unlike run_research(), nothing in vinu_research.sweep.
        run_sweep_candidate() catches InfrastructureError from
        `tools.run_backtest()` -- it propagates straight through. The old
        blanket `except Exception` here swallowed it and silently re-ran
        the whole candidate over HTTP (hitting the same 180s wall again)
        instead of surfacing the real "simulator down/rejecting" failure."""
        from vinu_research.tools import InfrastructureError

        fake_tools = MagicMock()
        fake_tools.close = AsyncMock()
        with patch("vinu_agent.broker.research_link.get_research_tools", return_value=fake_tools), \
                patch(
                    "vinu_research.sweep.run_sweep_candidate",
                    new=AsyncMock(side_effect=InfrastructureError("simulator down, do not retry")),
                ), \
                patch("httpx.post") as mock_post:
            with pytest.raises(InfrastructureError):
                _tool().execute(
                    symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
                    recipe="crossover", params='{"fast_period": 9, "slow_period": 40}',
                )
        mock_post.assert_not_called()


class TestRunSweepCandidateToolHttpFallback:
    def test_recipe_mode_uses_correct_url_and_payload(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"run_id": "abc"}'
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
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
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
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
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31", recipe="crossover", params="{}")
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8087/research/sweep/candidate"

    def test_optional_indicators_and_capital_passed_through(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
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
        with _force_in_process_unavailable(), patch("httpx.post", return_value=mock_resp):
            try:
                tool.execute(symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31", recipe="crossover", params="{}")
                assert False, "expected RuntimeError"
            except RuntimeError:
                pass


def _recipes_tool(services_config: dict | None = None) -> ListSweepRecipesTool:
    tool = ListSweepRecipesTool()
    tool._services_config = services_config or {}
    return tool


def _force_recipes_in_process_unavailable():
    return patch(
        "vinu_research.generator.list_recipe_details",
        side_effect=RuntimeError("not available"),
    )


class TestListSweepRecipesToolInProcess:
    def test_lists_real_built_in_recipes(self) -> None:
        result = json.loads(_recipes_tool().execute())
        assert len(result["recipes"]) > 0
        assert any(r["key"] == "crossover" for r in result["recipes"])

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _recipes_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"recipes": []}'
        with _force_recipes_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        mock_get.assert_called_once()
        assert result == '{"recipes": []}'


class TestListSweepRecipesToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _recipes_tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.text = '{"recipes": []}'
        with _force_recipes_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/sweep/recipes"
        assert result == '{"recipes": []}'

    def test_falls_back_to_default_url(self) -> None:
        tool = _recipes_tool()
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with _force_recipes_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/sweep/recipes"
