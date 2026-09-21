from __future__ import annotations

import json

from vinu_agent.tools.angle_glossary import ANGLE_GLOSSARY, explain_angle
from vinu_agent.tools.angles_tool import ExplainAngleTool


def test_every_real_angle_has_a_glossary_entry():
    """All 28 real angle ids from angles.yaml must be covered -- a
    missing one would silently fall back to the generic 'no entry'
    message instead of the intended explanation."""
    real_angle_ids = {
        "arima", "backtesting_44_metrics", "chronos", "dlinear",
        "drawdown_deep_dive", "exponential_smoothing", "garch",
        "itransformer", "kalman_filters", "kronos", "lag_llama",
        "lpatchtst", "lstm", "moirai", "moment", "news_price_causality",
        "patchtst", "peer_relative_strength", "pnl_attribution",
        "regime_analysis", "shock_clustering", "shock_personality",
        "tft", "timer_timerxl", "timesfm", "tips_regime_aware_transformer",
        "trend_lifecycle", "trend_session_structure",
    }
    assert real_angle_ids == set(ANGLE_GLOSSARY.keys())
    assert len(real_angle_ids) == 28


def test_every_blurb_is_real_content_not_empty():
    for name, blurb in ANGLE_GLOSSARY.items():
        assert isinstance(blurb, str) and len(blurb) > 20, name


def test_explain_angle_known_angle():
    text = explain_angle("shock_personality")
    assert "shock" in text.lower() or "load-bearing" in text.lower()


def test_explain_angle_unknown_angle_fails_open_not_raises():
    text = explain_angle("some_future_angle_not_yet_added")
    assert "no glossary entry" in text.lower()
    assert "some_future_angle_not_yet_added" in text


class TestExplainAngleTool:
    def test_execute_returns_one_blurb_per_requested_angle(self):
        tool = ExplainAngleTool()
        result = json.loads(tool.execute(angle_names=["arima", "kronos"]))
        assert set(result.keys()) == {"arima", "kronos"}
        assert "ARIMA" in result["arima"] or "classical" in result["arima"].lower()

    def test_execute_accepts_a_bare_string_not_just_a_list(self):
        tool = ExplainAngleTool()
        result = json.loads(tool.execute(angle_names="garch"))
        assert set(result.keys()) == {"garch"}

    def test_execute_unknown_angle_does_not_raise(self):
        tool = ExplainAngleTool()
        result = json.loads(tool.execute(angle_names=["not_a_real_angle"]))
        assert "no glossary entry" in result["not_a_real_angle"].lower()

    def test_execute_empty_list_returns_empty_object(self):
        tool = ExplainAngleTool()
        result = json.loads(tool.execute(angle_names=[]))
        assert result == {}

    def test_tool_is_auto_discoverable_as_a_basetool_subclass(self):
        """Registration is fully automatic (vinu_agent/tools/__init__.py's
        build_registry discovers every BaseTool subclass in this package)
        -- this just confirms the class shape that discovery relies on."""
        from vinu_agent.agent.tools import BaseTool

        assert issubclass(ExplainAngleTool, BaseTool)
        assert ExplainAngleTool.name == "explain_angle"
        assert ExplainAngleTool.__module__.startswith("vinu_agent.tools.")
