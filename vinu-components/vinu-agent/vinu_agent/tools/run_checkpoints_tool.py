from ..agent.tools import BaseTool


class RunCheckpointsTool(BaseTool):
    name = "get_run_checkpoints"
    description = (
        "Read iteration checkpoints saved during a research run — each "
        "iteration's strategy code, metrics, and critic verdict at the time "
        "it ran. Use latest_only=true to resume from where a previous run "
        "left off instead of starting a new search from scratch. Note: as of "
        "this tool's introduction, checkpoints are saved every iteration but "
        "nothing automatically resumes from them — resuming is a decision the "
        "caller makes explicitly using this data."
    )
    parameters = {
        "type": "object",
        "properties": {
            "run_id": {"type": "integer", "description": "Research run ID (from run_research's response or list_runs)"},
            "latest_only": {
                "type": "boolean",
                "description": "Return only the most recent checkpoint instead of the full list (optional, default false)",
            },
        },
        "required": ["run_id"],
    }
    is_readonly = True

    def __init__(self):
        self._services_config = {}

    def execute(self, **kwargs) -> str:
        import httpx

        url = self._services_config.get("vinu_research", "http://localhost:8087")
        params = {}
        if kwargs.get("latest_only"):
            params["latest_only"] = True

        resp = httpx.get(
            f"{url}/research/runs/{kwargs['run_id']}/checkpoints",
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.text
