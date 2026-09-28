"""item #11 finding #2: load_skill_tool.py had zero test coverage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from vinu_agent.tools.load_skill_tool import LoadSkillTool


class TestLoadSkillTool:
    def test_no_skills_loader_returns_error(self) -> None:
        tool = LoadSkillTool()
        result = json.loads(tool.execute(name="research-discipline"))
        assert result["status"] == "error"

    def test_unknown_skill_returns_error(self) -> None:
        tool = LoadSkillTool()
        tool._skills_loader = MagicMock(get_content=MagicMock(return_value=None))
        result = json.loads(tool.execute(name="not-a-real-skill"))
        assert result["status"] == "error"
        assert "not-a-real-skill" in result["error"]

    def test_known_skill_returns_its_content(self) -> None:
        tool = LoadSkillTool()
        tool._skills_loader = MagicMock(get_content=MagicMock(return_value="# Research Discipline\n..."))
        result = json.loads(tool.execute(name="research-discipline"))
        assert result["status"] == "ok"
        assert result["name"] == "research-discipline"
        assert result["content"] == "# Research Discipline\n..."
