"""The orchestrator's one delegation tool: hand a task to a whole team
(manager + its specialists) and get back one bounded, structured result.
See New-talk-agents/01-orchestrator-and-teams-architecture.md."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..agent.team import TeamManager
from ..agent.tools import BaseTool

LOG = logging.getLogger(__name__)


class DelegateToTeamTool(BaseTool):
    name = "delegate_to_team"
    description = (
        "Delegate a task to a specialized team (manager + its own specialist agents) and "
        "get back one bounded result. Use this for work that needs a team's real multi-step "
        "process (e.g. researching a new trading strategy) -- for anything you can answer "
        "yourself with your own tools, just answer directly instead of delegating."
    )
    parameters = {
        "type": "object",
        "properties": {
            "team_name": {"type": "string", "description": "Which team to delegate to, e.g. 'research'"},
            "task": {"type": "string", "description": "The task/question for the team"},
        },
        "required": ["team_name", "task"],
    }
    is_readonly = False
    repeatable = True

    def __init__(self) -> None:
        self._teams_dir: str = ""
        self._full_registry: Any = None
        self._llm: Any = None
        self._skills_loader: Any = None
        self._event_callback: Any = None
        self._run_store: Any = None
        self._llm_call_store: Any = None
        self._session_id: str = ""
        self._strategy_store: Any = None
        self._ticker_summary_store: Any = None
        self._ticker_ledger_store: Any = None
        self._services_config: dict = {}

    def execute(self, **kwargs: Any) -> str:
        team_name = kwargs.get("team_name", "")
        task = kwargs.get("task", "")

        if not self._teams_dir:
            return json.dumps({"status": "error", "error": "teams_dir not configured"})
        if self._full_registry is None or self._llm is None:
            return json.dumps({"status": "error", "error": "delegate_to_team not fully wired (missing registry/llm)"})

        team_dir = Path(self._teams_dir) / team_name
        if not (team_dir / "TEAM.md").exists():
            available = sorted(
                p.name for p in Path(self._teams_dir).iterdir()
                if p.is_dir() and (p / "TEAM.md").exists()
            ) if Path(self._teams_dir).exists() else []
            return json.dumps({
                "status": "error",
                "error": f"Unknown team {team_name!r}. Available: {available}",
            })

        try:
            manager = TeamManager(
                team_dir,
                full_registry=self._full_registry,
                llm=self._llm,
                skills_loader=self._skills_loader,
                event_callback=self._event_callback,
                run_store=self._run_store,
                llm_call_store=self._llm_call_store,
                triggered_by_session_id=self._session_id,
                strategy_store=self._strategy_store,
                ticker_summary_store=self._ticker_summary_store,
                ticker_ledger_store=self._ticker_ledger_store,
                services_config=self._services_config,
            )
            result = manager.run(task)
        except Exception as exc:
            LOG.exception("delegate_to_team failed for team %r", team_name)
            return json.dumps({"status": "error", "team": team_name, "error": str(exc)})

        # Bounded, structured result only -- never the manager's/specialists'
        # raw trace. See the architecture doc's context-discipline rule.
        return json.dumps({
            "status": result.get("status", "completed"),
            "team": team_name,
            "run_id": result.get("run_id", ""),
            "content": result.get("content", ""),
        })
