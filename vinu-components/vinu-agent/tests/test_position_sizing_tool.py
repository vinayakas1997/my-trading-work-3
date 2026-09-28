"""item #11 finding #2: position_sizing_tool.py had zero test coverage.
The underlying math (`agent/position_sizing.py::compute_position_size`)
already has its own tests (test_position_sizing.py) -- these exercise
this tool's own wrapper logic: config fallback resolution, optional-field
parsing, and delegation, not the sizing formulas themselves."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import patch

from vinu_agent.tools.position_sizing_tool import ComputePositionSizeTool


class TestComputePositionSizeTool:
    def test_delegates_to_compute_position_size_with_parsed_inputs(self) -> None:
        tool = ComputePositionSizeTool()
        tool._config = SimpleNamespace(
            position_sizing_method="fractional_kelly",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with patch(
            "vinu_agent.tools.position_sizing_tool.compute_position_size",
            return_value={"status": "ok", "size": 1000.0},
        ) as mock_compute:
            result = json.loads(tool.execute(
                account_equity=100_000, win_rate=0.6, payoff_ratio=1.5,
            ))
        assert result == {"status": "ok", "size": 1000.0}
        kwargs = mock_compute.call_args.kwargs
        assert kwargs["account_equity"] == 100_000.0
        assert kwargs["win_rate"] == 0.6
        assert kwargs["payoff_ratio"] == 1.5
        assert kwargs["method"] == "fractional_kelly"

    def test_explicit_method_overrides_config_default(self) -> None:
        tool = ComputePositionSizeTool()
        tool._config = SimpleNamespace(
            position_sizing_method="fractional_kelly",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with patch(
            "vinu_agent.tools.position_sizing_tool.compute_position_size",
            return_value={"status": "ok"},
        ) as mock_compute:
            tool.execute(account_equity=100_000, method="atr_stop")
        assert mock_compute.call_args.kwargs["method"] == "atr_stop"

    def test_no_config_falls_back_to_load_config(self) -> None:
        tool = ComputePositionSizeTool()
        tool._config = None
        fake_cfg = SimpleNamespace(
            position_sizing_method="fixed_fractional",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with (
            patch("vinu_agent.tools.position_sizing_tool._load_default_config", return_value=fake_cfg),
            patch(
                "vinu_agent.tools.position_sizing_tool.compute_position_size",
                return_value={"status": "ok"},
            ) as mock_compute,
        ):
            tool.execute(account_equity=50_000)
        assert mock_compute.call_args.kwargs["method"] == "fixed_fractional"

    def test_optional_fields_absent_are_passed_as_none_not_zero(self) -> None:
        """cvar_95/current_vol/forecast_confidence absent must mean 'not
        computed' (None), never silently coerced to 0.0 -- 0.0 would be
        indistinguishable from a real zero-risk/zero-confidence reading."""
        tool = ComputePositionSizeTool()
        tool._config = SimpleNamespace(
            position_sizing_method="fractional_kelly",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with patch(
            "vinu_agent.tools.position_sizing_tool.compute_position_size",
            return_value={"status": "ok"},
        ) as mock_compute:
            tool.execute(account_equity=100_000)
        kwargs = mock_compute.call_args.kwargs
        assert kwargs["cvar_95"] is None
        assert kwargs["current_vol"] is None
        assert kwargs["forecast_confidence"] is None

    def test_optional_fields_present_are_parsed_as_floats(self) -> None:
        tool = ComputePositionSizeTool()
        tool._config = SimpleNamespace(
            position_sizing_method="fractional_kelly",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with patch(
            "vinu_agent.tools.position_sizing_tool.compute_position_size",
            return_value={"status": "ok"},
        ) as mock_compute:
            tool.execute(
                account_equity=100_000, cvar_95=0.0, current_vol=0.015, forecast_confidence=0.7,
            )
        kwargs = mock_compute.call_args.kwargs
        assert kwargs["cvar_95"] == 0.0
        assert kwargs["current_vol"] == 0.015
        assert kwargs["forecast_confidence"] == 0.7

    def test_unparseable_optional_field_falls_back_to_none(self) -> None:
        tool = ComputePositionSizeTool()
        tool._config = SimpleNamespace(
            position_sizing_method="fractional_kelly",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with patch(
            "vinu_agent.tools.position_sizing_tool.compute_position_size",
            return_value={"status": "ok"},
        ) as mock_compute:
            tool.execute(account_equity=100_000, cvar_95="not-a-number")
        assert mock_compute.call_args.kwargs["cvar_95"] is None

    def test_zero_account_equity_still_delegates_not_short_circuited_here(self) -> None:
        """Fail-safe (size 0 on non-positive equity) lives in
        compute_position_size itself -- this tool must not duplicate that
        check, just pass the value through."""
        tool = ComputePositionSizeTool()
        tool._config = SimpleNamespace(
            position_sizing_method="fractional_kelly",
            kelly_fraction=0.25,
            risk_per_trade_pct=0.02,
            atr_stop_multiple=2.0,
        )
        with patch(
            "vinu_agent.tools.position_sizing_tool.compute_position_size",
            return_value={"status": "ok", "size": 0.0},
        ) as mock_compute:
            tool.execute(account_equity=0)
        assert mock_compute.call_args.kwargs["account_equity"] == 0.0
