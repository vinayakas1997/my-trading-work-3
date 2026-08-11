"""Confirms Phase 6's structural restrictions (New-talk-agents/
new-thinking/new-restructure/phases/phase-6-thesis-intake/) -- theory_
reviewer cannot write code (by omission from its tool list, not a prompt
instruction), and submit_thesis stays orchestrator-only, not leaking into
any team's scoped registry. Walks the real teams/ directory, mirroring
test_phase1_sweep_tool_scoping.py's pattern.
"""

from __future__ import annotations

from pathlib import Path

from vinu_agent.agent.team import load_agent_spec, load_team_spec

TEAMS_DIR = Path(__file__).parent.parent / "teams"

_CODE_EXECUTION_TOOL_NAMES = {"run_backtest", "run_parameter_sweep", "run_sweep_candidate"}


def _all_agent_specs(team_dir: Path):
    for agent_dir in sorted((team_dir / "agents").iterdir()):
        if agent_dir.is_dir():
            yield load_agent_spec(agent_dir)


class TestTheoryReviewerCannotWriteCode:
    def test_thesis_intake_tool_list_excludes_code_execution(self) -> None:
        spec = load_agent_spec(TEAMS_DIR / "thesis_intake" / "agents" / "theory_reviewer")
        assert not (set(spec.tools) & _CODE_EXECUTION_TOOL_NAMES)

    def test_thesis_intake_manager_tools_exclude_code_execution_too(self) -> None:
        spec = load_team_spec(TEAMS_DIR / "thesis_intake")
        assert not (set(spec.tools) & _CODE_EXECUTION_TOOL_NAMES)

    def test_theory_reviewer_has_the_real_evidence_tools(self) -> None:
        spec = load_agent_spec(TEAMS_DIR / "thesis_intake" / "agents" / "theory_reviewer")
        for expected in ("get_all_angles", "get_ticker_summary", "query_hypotheses", "load_skill"):
            assert expected in spec.tools


class TestSubmitThesisScopedToOrchestratorOnly:
    def test_no_team_lists_submit_thesis_in_its_tools(self) -> None:
        """submit_thesis constructs TeamManager instances directly (like
        delegate_to_team does) -- it must never be handed to a team's own
        specialist, which would let a nested agent recursively submit
        theories rather than the top-level orchestrator alone."""
        offenders = []
        for team_dir in sorted(TEAMS_DIR.iterdir()):
            if not team_dir.is_dir() or not (team_dir / "agents").exists():
                continue
            team_spec = load_team_spec(team_dir)
            if "submit_thesis" in team_spec.tools:
                offenders.append(f"{team_dir.name} (manager)")
            for spec in _all_agent_specs(team_dir):
                if "submit_thesis" in spec.tools:
                    offenders.append(f"{team_dir.name}/{spec.name}")
        assert offenders == []
