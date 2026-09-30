"""B1 fix: the live_decision agent's declared tools must all resolve in
the real tool registry (an unregistered name is silently skipped by
subset(), which would leave the agent without the input the prompt tells
it to use), and the prompt/manager files must carry the section anchors
this fix added."""

from __future__ import annotations

from pathlib import Path

from vinu_agent.agent.team import load_agent_spec
from vinu_agent.tools import build_registry

TEAMS_DIR = Path(__file__).parent.parent / "teams"
AGENT_DIR = TEAMS_DIR / "live_decision" / "agents" / "live_decision_agent"


class TestLiveDecisionAgentWiring:
    def test_every_declared_tool_resolves_in_the_real_registry(self) -> None:
        spec = load_agent_spec(AGENT_DIR)
        assert "get_reflection_synthesis" in spec.tools
        registry = build_registry()
        scoped = registry.subset(spec.tools)
        assert len(scoped.all_tools()) == len(spec.tools)

    def test_prompt_covers_the_new_context_inputs(self) -> None:
        prompt = (AGENT_DIR / "prompt.md").read_text(encoding="utf-8")
        for anchor in (
            "maturity_status",
            "get_reflection_synthesis",
            "unconfirmed_moves",
            "reflection_notes",
            "correlation/drawdown",
        ):
            assert anchor in prompt

    def test_manager_json_carries_tier_evidence_and_prior_verdict(self) -> None:
        manager = (TEAMS_DIR / "live_decision" / "manager_prompt.md").read_text(encoding="utf-8")
        for anchor in (
            '"tier"',
            '"evidence_summary"',
            '"past_decision_noted"',
            "never computed",
        ):
            assert anchor in manager


class TestIdeaGeneratorWiring:
    """B2 fix: the idea_generator's checklist inputs must all resolve in
    the real registry, and the prompt must carry the checklist."""

    def test_every_declared_tool_resolves_in_the_real_registry(self) -> None:
        agent_dir = TEAMS_DIR / "research" / "agents" / "idea_generator"
        spec = load_agent_spec(agent_dir)
        for name in ("get_signal_evidence", "query_hypotheses", "get_correlation"):
            assert name in spec.tools
        registry = build_registry()
        scoped = registry.subset(spec.tools)
        assert len(scoped.all_tools()) == len(spec.tools)

    def test_prompt_carries_the_required_context_checklist(self) -> None:
        agent_dir = TEAMS_DIR / "research" / "agents" / "idea_generator"
        prompt = (agent_dir / "prompt.md").read_text(encoding="utf-8")
        for anchor in (
            "Required context before drafting",
            "get_reflection_synthesis",
            "get_signal_evidence(symbol=symbol)",
            "query_hypotheses(symbol=symbol)",
            "Regime citation",
            "get_correlation",
            "consulted-or-unknown",
        ):
            assert anchor in prompt
