from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class WorkflowStep:
    skill_name: str
    status: str = "pending"  # pending | active | completed

    def to_dict(self) -> dict[str, Any]:
        return {"skill_name": self.skill_name, "status": self.status}


class WorkflowTracker:
    def __init__(self) -> None:
        self._steps: list[WorkflowStep] = []
        self._current_index: int = -1

    def plan(self, skill_names: list[str]) -> str:
        self._steps = [WorkflowStep(name) for name in skill_names]
        self._current_index = 0 if self._steps else -1
        if self._steps:
            self._steps[0].status = "active"
        return (
            f"Workflow planned: {len(self._steps)} step(s). "
            f"Current: {self._steps[0].skill_name if self._steps else 'none'}"
        )

    def complete_current(self) -> str:
        if self._current_index < 0 or self._current_index >= len(self._steps):
            return "No active step to complete."
        self._steps[self._current_index].status = "completed"
        self._current_index += 1
        if self._current_index < len(self._steps):
            self._steps[self._current_index].status = "active"
            return f"Completed. Next step: {self._steps[self._current_index].skill_name}"
        return "All steps completed."

    def get_summary(self) -> str:
        if not self._steps:
            return "No workflow planned."
        lines = [s.to_dict() for s in self._steps]
        return f"Workflow ({len(self._steps)} steps): {lines}"

    def all_completed(self) -> bool:
        return bool(self._steps) and all(s.status == "completed" for s in self._steps)

    def to_context_block(self) -> str:
        if not self._steps:
            return ""
        lines = ["<workflow>"]
        for s in self._steps:
            active = " <-- CURRENT" if s.status == "active" else ""
            done = " ✓" if s.status == "completed" else ""
            lines.append(f"  {s.skill_name}: {s.status}{done}{active}")
        lines.append("</workflow>")
        return "\n".join(lines)
