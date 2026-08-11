"""Confirms get_portfolio_concentration (component-consolidation-plan.md:
wiring risk_gatekeeper's exposure check to a real vinu-portfolio engine)
is wired into risk_gatekeeper's exposure_reviewer specialist and nowhere
else -- same real-teams-directory scoping proof as
test_phase1_sweep_tool_scoping.py. See
vinu_agent/tools/portfolio_concentration_tool.py.
"""

from __future__ import annotations

from pathlib import Path

from vinu_agent.agent.team import load_agent_spec
from vinu_agent.tools import build_registry

TEAMS_DIR = Path(__file__).parent.parent / "teams"


def _all_agent_specs(team_dir: Path):
    for agent_dir in sorted((team_dir / "agents").iterdir()):
        if agent_dir.is_dir():
            yield load_agent_spec(agent_dir)


class TestPortfolioConcentrationToolScoping:
    def test_exposure_reviewer_has_both_portfolio_tools(self) -> None:
        spec = load_agent_spec(TEAMS_DIR / "risk_gatekeeper" / "agents" / "exposure_reviewer")
        assert "get_portfolio" in spec.tools
        assert "get_portfolio_concentration" in spec.tools

    def test_tool_is_globally_discoverable_but_scoped_to_exposure_reviewer_only(self) -> None:
        registry = build_registry()
        full_names = {t.name for t in registry.all_tools()}
        assert "get_portfolio_concentration" in full_names  # globally discoverable

        agents_listing_it = []
        for team_dir in sorted(TEAMS_DIR.iterdir()):
            if not team_dir.is_dir() or not (team_dir / "agents").exists():
                continue
            for spec in _all_agent_specs(team_dir):
                if "get_portfolio_concentration" in spec.tools:
                    agents_listing_it.append(f"{team_dir.name}/{spec.name}")

        assert agents_listing_it == ["risk_gatekeeper/exposure_reviewer"]
