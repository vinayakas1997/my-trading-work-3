"""Tests for BacktestTool -- regression coverage for the 2 real bugs found
and fixed via a real-LLM/real-simulator test run (interval case,
run_validation never being requested). See
New-talk-agents/new-thinking/agentic-e2e-twst-files-and-status/01-findings-and-status.md.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.tools.backtest_tool import BacktestTool


def _tool() -> BacktestTool:
    tool = BacktestTool()
    tool._services_config = {"vinu_simulator": "http://localhost:8085"}
    return tool


class TestBacktestToolPayload:
    def test_interval_defaults_to_lowercase(self) -> None:
        """The real simulator rejects "1D" -- only lowercase interval codes
        are valid. Regression test for that real bug."""
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            _tool().execute(
                strategy_code="class Strategy(BaseStrategy): pass",
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["interval"] == "1d"

    def test_explicit_interval_passed_through_unchanged(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            _tool().execute(
                strategy_code="class Strategy(BaseStrategy): pass",
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
                interval="1h",
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["interval"] == "1h"

    def test_run_validation_always_requested(self) -> None:
        """Was silently defaulting to off (the simulator's own default),
        meaning risk_critic's PASS/STOP verdict had zero statistical-
        overfitting evidence behind it. Regression test for that real gap."""
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            _tool().execute(
                strategy_code="class Strategy(BaseStrategy): pass",
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["run_validation"] is True

    def test_posts_to_configured_simulator_url(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            _tool().execute(
                strategy_code="class Strategy(BaseStrategy): pass",
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
            )
        args, _ = mock_post.call_args
        assert args[0] == "http://localhost:8085/simulator/simulate/custom"

    def test_indicators_defaults_when_omitted(self) -> None:
        """Regression test: run_backtest previously had no indicators param
        at all, so generate_weights only ever saw sma_20/sma_50/rsi_14 no
        matter what the LLM referenced. Default preserves that baseline."""
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            _tool().execute(
                strategy_code="class Strategy(BaseStrategy): pass",
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["indicators"] == ["sma_20", "sma_50", "rsi_14"]

    def test_indicators_passed_through_when_given(self) -> None:
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            _tool().execute(
                strategy_code="class Strategy(BaseStrategy): pass",
                symbol="AAPL", start_date="2025-01-01", end_date="2025-06-01",
                indicators=["rsi_14", "adx_14"],
            )
        payload = mock_post.call_args.kwargs["json"]
        assert payload["indicators"] == ["rsi_14", "adx_14"]
