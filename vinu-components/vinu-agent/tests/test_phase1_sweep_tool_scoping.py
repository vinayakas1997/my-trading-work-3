"""Confirms Phase 1's new sweep tools (New-talk-agents/new-thinking/
new-restructure/phases/phase-1-sweep-engine-wiring/) are wired into the
research team's own specialists and nowhere else -- registering a tool in
build_registry() makes it globally DISCOVERABLE, but each specialist's own
AGENT.md `tools:` list is what actually scopes what it can call (see
agent/team.py's DelegateToAgentTool -- ToolRegistry.subset(spec.tools)).
This walks the real teams/ directory, not synthetic fixtures.
"""

from __future__ import annotations

from pathlib import Path

from vinu_agent.agent.team import load_agent_spec, load_team_spec
from vinu_agent.tools import build_registry

TEAMS_DIR = Path(__file__).parent.parent / "teams"
SWEEP_TOOL_NAMES = {"run_sweep_candidate", "list_sweep_recipes", "run_parameter_sweep"}


def _all_agent_specs(team_dir: Path):
    for agent_dir in sorted((team_dir / "agents").iterdir()):
        if agent_dir.is_dir():
            yield load_agent_spec(agent_dir)


class TestSweepToolsScopedToResearchTeamOnly:
    def test_idea_generator_has_list_sweep_recipes_not_run_parameter_sweep(self) -> None:
        spec = load_agent_spec(TEAMS_DIR / "research" / "agents" / "idea_generator")
        assert "list_sweep_recipes" in spec.tools
        assert "run_parameter_sweep" not in spec.tools
        assert "run_sweep_candidate" not in spec.tools

    def test_backtest_runner_has_run_parameter_sweep_and_run_backtest(self) -> None:
        spec = load_agent_spec(TEAMS_DIR / "research" / "agents" / "backtest_runner")
        assert "run_parameter_sweep" in spec.tools
        assert "run_backtest" in spec.tools

    def test_research_manager_team_tools_do_not_include_sweep_tools_directly(self) -> None:
        """The manager delegates, it doesn't call these tools itself --
        TEAM.md's own tools: list should stay empty/unrelated, per
        manager_prompt.md ('you do not write strategy code or run
        backtests yourself')."""
        spec = load_team_spec(TEAMS_DIR / "research")
        assert not (set(spec.tools) & SWEEP_TOOL_NAMES)

    def test_screener_team_agents_do_not_have_sweep_tools(self) -> None:
        for spec in _all_agent_specs(TEAMS_DIR / "screener"):
            assert not (set(spec.tools) & SWEEP_TOOL_NAMES), (
                f"{spec.name} unexpectedly has sweep tools: {set(spec.tools) & SWEEP_TOOL_NAMES}"
            )

    def test_sweep_tools_are_globally_discoverable_but_only_research_specialists_request_them(self) -> None:
        """build_registry() auto-discovers every BaseTool subclass in
        tools/ (that's the DISCOVERY mechanism) -- confirm the new tools
        are in the full registry, then confirm the only two AGENT.md files
        across the whole teams/ directory that list them are the two
        research specialists, proving scoping happens at the AGENT.md
        level, not by omitting registration."""
        registry = build_registry()
        full_names = {t.name for t in registry.all_tools()}
        assert SWEEP_TOOL_NAMES <= full_names  # globally discoverable

        agents_listing_sweep_tools = []
        for team_dir in sorted(TEAMS_DIR.iterdir()):
            if not team_dir.is_dir() or not (team_dir / "agents").exists():
                continue
            for spec in _all_agent_specs(team_dir):
                if set(spec.tools) & SWEEP_TOOL_NAMES:
                    agents_listing_sweep_tools.append(f"{team_dir.name}/{spec.name}")

        assert set(agents_listing_sweep_tools) == {
            "research/idea_generator", "research/backtest_runner",
        }
