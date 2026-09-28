"""item #11 finding #2: plan_workflow_tool.py had zero test coverage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from vinu_agent.tools.plan_workflow_tool import PlanWorkflowTool


class TestPlanWorkflowTool:
    def test_no_workflow_tracker_returns_error(self) -> None:
        tool = PlanWorkflowTool()
        result = json.loads(tool.execute(skills=["research-strategy"]))
        assert result["status"] == "error"

    def test_no_skills_provided_returns_error(self) -> None:
        tool = PlanWorkflowTool()
        tool._workflow_tracker = MagicMock()
        result = json.loads(tool.execute(skills=[]))
        assert result["status"] == "error"
        tool._workflow_tracker.plan.assert_not_called()

    def test_valid_plan_calls_tracker_and_reports_steps(self) -> None:
        tool = PlanWorkflowTool()
        tool._workflow_tracker = MagicMock(plan=MagicMock(return_value="plan recorded"))
        result = json.loads(tool.execute(skills=["research-strategy", "generate-trade-plan"]))
        assert result["status"] == "ok"
        assert result["n_steps"] == 2
        assert result["steps"] == ["research-strategy", "generate-trade-plan"]
        assert result["message"] == "plan recorded"
        tool._workflow_tracker.plan.assert_called_once_with(["research-strategy", "generate-trade-plan"])
