import json
from ..agent.tools import BaseTool


class PlanWorkflowTool(BaseTool):
    name = "plan_workflow"
    description = "Plan a multi-step workflow by listing skill names in execution order. Call this before loading skills to declare your plan."
    parameters = {
        "type": "object",
        "properties": {
            "skills": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ordered list of skill names to execute (e.g., ['research-strategy', 'generate-trade-plan'])",
            },
        },
        "required": ["skills"],
    }
    is_readonly = True

    def __init__(self):
        self._workflow_tracker = None

    def execute(self, **kwargs) -> str:
        tracker = getattr(self, "_workflow_tracker", None)
        if tracker is None:
            return json.dumps({"status": "error", "error": "Workflow tracker not available"})
        skills = kwargs.get("skills", [])
        if not skills:
            return json.dumps({"status": "error", "error": "No skills provided"})
        msg = tracker.plan(skills)
        return json.dumps({"status": "ok", "n_steps": len(skills), "steps": skills, "message": msg})
