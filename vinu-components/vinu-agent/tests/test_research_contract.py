"""item #17's own unnumbered "confirmed gap, not a new item": no contract/
schema test anywhere between agent<->research<->simulator, despite the
seam's own 4 numbered findings all being closed. This is that test, for
the agent<->research hop specifically (see vinu-research's own
test_simulator_contract.py for the research<->simulator hop).

Approach: exercise each tool's REAL payload-building code (via the same
HTTP-fallback path every other test in this suite already forces with
_force_in_process_unavailable()) and validate the *actual* dict it
builds against vinu-research's own real pydantic request model -- not a
hand-copied literal of what the schema "should" look like, which could
drift from either side silently the way item #16 finding #4 and this
exact seam already warned about elsewhere in this audit."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_agent.tools.research_tool import ResearchTool
from vinu_agent.tools.run_sweep_candidate_tool import (
    RunSweepCandidateTool,
    _serialize_sweep_candidate,
)
from vinu_research.server.routes_read import RunResearchRequest
from vinu_research.server.routes_sweep import SweepCandidateRequest, _serialize


def _force_research_tool_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_research_service",
        side_effect=ImportError("vinu_research not installed"),
    )


def _force_sweep_tool_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_research_tools",
        side_effect=ImportError("vinu_research not installed"),
    )


class TestResearchToolPayloadMatchesRealRequestSchema:
    def _captured_payload(self, **kwargs) -> dict:
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        tool = ResearchTool()
        tool._services_config = {}
        with _force_research_tool_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(**kwargs)
        _, call_kwargs = mock_post.call_args
        return call_kwargs["json"]

    def test_required_fields_only_validates(self) -> None:
        payload = self._captured_payload(
            idea="trend-following", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31",
        )
        RunResearchRequest(**payload)  # raises pydantic.ValidationError on any drift

    def test_every_optional_field_set_still_validates(self) -> None:
        payload = self._captured_payload(
            idea="trend-following", symbol="AAPL", from_date="2024-01-01", to_date="2024-12-31",
            indicators="sma_20,rsi_14", initial_capital=50000, universe="MSFT,GOOGL", dry_run=True,
        )
        req = RunResearchRequest(**payload)
        assert req.indicators == ["sma_20", "rsi_14"]
        assert req.universe == ["MSFT", "GOOGL"]
        assert req.dry_run is True


class TestSweepCandidateToolPayloadMatchesRealRequestSchema:
    def _captured_payload(self, **kwargs) -> dict:
        mock_resp = MagicMock()
        mock_resp.text = "{}"
        tool = RunSweepCandidateTool()
        tool._services_config = {}
        with _force_sweep_tool_unavailable(), patch("httpx.post", return_value=mock_resp) as mock_post:
            tool.execute(**kwargs)
        _, call_kwargs = mock_post.call_args
        return call_kwargs["json"]

    def test_recipe_mode_payload_validates(self) -> None:
        payload = self._captured_payload(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            recipe="crossover", params='{"fast_period": 9, "slow_period": 40}',
        )
        SweepCandidateRequest(**payload)

    def test_base_code_mode_payload_validates(self) -> None:
        payload = self._captured_payload(
            symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31",
            base_code="class UserStrategy: ...", param_name="fast_period", param_value=9,
        )
        SweepCandidateRequest(**payload)

    def test_neither_mode_set_fails_the_same_validator_the_real_route_would_apply(self) -> None:
        # A malformed tool call (LLM omitted both modes) should fail the
        # exact same "exactly one mode" rule the real route enforces, not
        # silently pass a payload the server would then 422 on.
        payload = self._captured_payload(symbol="AAPL", from_date="2023-01-01", to_date="2023-12-31")
        import pytest
        with pytest.raises(Exception):
            SweepCandidateRequest(**payload)


class TestSerializeSweepCandidateMatchesRouteSerialization:
    """run_sweep_candidate_tool.py's own comment claims
    `_serialize_sweep_candidate()` is "exactly routes_sweep.py's own
    `_serialize` shape" -- a hand-duplicated copy that could drift
    silently if either side changed alone. This proves the claim rather
    than trusting the comment."""

    def test_key_sets_are_identical(self) -> None:
        result = MagicMock()
        result.run_id = "r1"
        result.strategy_name = "s"
        result.strategy_code = "code"
        result.params_used = {}
        result.metrics = {}
        result.trade_count = 0
        result.validation = None

        tool_side = _serialize_sweep_candidate(result)
        route_side = _serialize(result)
        assert set(tool_side.keys()) == set(route_side.keys())
        assert tool_side == route_side
