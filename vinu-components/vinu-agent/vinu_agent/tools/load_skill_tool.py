import json
from ..agent.tools import BaseTool


class LoadSkillTool(BaseTool):
    name = "load_skill"
    description = "Load full documentation for a specialized research skill or methodology"
    parameters = {
        "name": {"type": "string", "description": "Skill name (e.g., strategy-generate, research-discipline)"},
    }
    is_readonly = True

    def execute(self, **kwargs) -> str:
        skills_loader = getattr(self, "_skills_loader", None)
        if skills_loader is None:
            return json.dumps({"status": "error", "error": "Skills loader not available"})
        content = skills_loader.get_content(kwargs["name"])
        if content is None:
            return json.dumps({"status": "error", "error": f"Skill '{kwargs['name']}' not found"})
        return json.dumps({"status": "ok", "name": kwargs["name"], "content": content})
