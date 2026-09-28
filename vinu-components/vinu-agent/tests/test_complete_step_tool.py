"""item #11 finding #2: complete_step_tool.py had zero test coverage."""

from __future__ import annotations

import json
from unittest.mock import MagicMock

from vinu_agent.tools.complete_step_tool import CompleteStepTool


class TestCompleteStepTool:
    def test_no_workflow_tracker_returns_error(self) -> None:
        tool = CompleteStepTool()
        result = json.loads(tool.execute())
        assert result["status"] == "error"

    def test_completes_current_step_via_tracker(self) -> None:
        tool = CompleteStepTool()
        tool._workflow_tracker = MagicMock(complete_current=MagicMock(return_value="step 1 done"))
        result = json.loads(tool.execute())
        assert result["status"] == "ok"
        assert result["message"] == "step 1 done"
        tool._workflow_tracker.complete_current.assert_called_once()
