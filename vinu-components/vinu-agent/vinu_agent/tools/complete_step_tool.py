import json
from ..agent.tools import BaseTool


class CompleteStepTool(BaseTool):
    name = "complete_step"
    description = "Mark the current workflow step as completed and move to the next one. Call this after finishing each skill in your plan."
    parameters = {}
    is_readonly = True

    def __init__(self):
        self._workflow_tracker = None

    def execute(self, **kwargs) -> str:
        tracker = getattr(self, "_workflow_tracker", None)
        if tracker is None:
            return json.dumps({"status": "error", "error": "Workflow tracker not available"})
        msg = tracker.complete_current()
        return json.dumps({"status": "ok", "message": msg})
