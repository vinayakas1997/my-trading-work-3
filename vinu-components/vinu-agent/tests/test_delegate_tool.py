import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from vinu_agent.agent.tools import ToolRegistry
from vinu_agent.tools.delegate_tool import DelegateToTeamTool


class FakeLLM:
    def __init__(self, responses: Optional[List[Dict]] = None):
        self.responses = responses or []
        self.call_count = 0

    def chat(self, messages: List[Dict], tools: Optional[List[Dict]] = None) -> Dict:
        if self.call_count < len(self.responses):
            resp = self.responses[self.call_count]
            self.call_count += 1
            return resp
        return {"content": "fallback"}


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _make_teams_dir(tmp_path: Path) -> Path:
    teams_dir = tmp_path / "teams"
    team_dir = teams_dir / "widget"
    _write(team_dir / "TEAM.md", """---
name: widget
manager_prompt_file: manager_prompt.md
tools: []
skills: []
---
""")
    _write(team_dir / "manager_prompt.md", "You manage the widget team.")
    return teams_dir


class TestDelegateToTeamTool:
    def test_not_configured_returns_error(self) -> None:
        tool = DelegateToTeamTool()
        result = json.loads(tool.execute(team_name="widget", task="x"))
        assert result["status"] == "error"
        assert "teams_dir" in result["error"]

    def test_missing_registry_or_llm_returns_error(self, tmp_path: Path) -> None:
        tool = DelegateToTeamTool()
        tool._teams_dir = str(_make_teams_dir(tmp_path))
        result = json.loads(tool.execute(team_name="widget", task="x"))
        assert result["status"] == "error"
        assert "not fully wired" in result["error"]

    def test_unknown_team_lists_available_teams(self, tmp_path: Path) -> None:
        tool = DelegateToTeamTool()
        tool._teams_dir = str(_make_teams_dir(tmp_path))
        tool._full_registry = ToolRegistry()
        tool._llm = FakeLLM()
        result = json.loads(tool.execute(team_name="does_not_exist", task="x"))
        assert result["status"] == "error"
        assert result["error"].startswith("Unknown team")
        assert "widget" in result["error"]

    def test_successful_delegation_returns_bounded_result(self, tmp_path: Path) -> None:
        tool = DelegateToTeamTool()
        tool._teams_dir = str(_make_teams_dir(tmp_path))
        tool._full_registry = ToolRegistry()
        tool._llm = FakeLLM([{"content": "VERDICT: PASS"}])

        result = json.loads(tool.execute(team_name="widget", task="do something"))

        assert result["status"] == "completed"
        assert result["team"] == "widget"
        assert result["content"] == "VERDICT: PASS"
        # Bounded result only -- no raw trace/history should leak through.
        assert "trace" not in result
        assert "history" not in result

    def test_team_manager_exception_returns_error_json_not_raise(self, tmp_path: Path) -> None:
        teams_dir = tmp_path / "teams"
        # A team dir with no TEAM.md at all under a name that otherwise looks
        # plausible -- exercised via a broken manager_prompt_file reference
        # instead, to force a real exception path inside TeamManager().
        team_dir = teams_dir / "broken"
        _write(team_dir / "TEAM.md", "---\nname: broken\nprompt_file: missing.md\n---\n")

        tool = DelegateToTeamTool()
        tool._teams_dir = str(teams_dir)
        tool._full_registry = ToolRegistry()
        tool._llm = FakeLLM()

        result = json.loads(tool.execute(team_name="broken", task="x"))
        assert result["status"] == "error"
        assert result["team"] == "broken"
