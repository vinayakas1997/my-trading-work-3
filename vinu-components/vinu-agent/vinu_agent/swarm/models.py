import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class RunStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


@dataclass
class SwarmTask:
    task_id: str = field(default_factory=_new_id)
    run_id: str = ""
    agent_name: str = ""
    role: str = ""
    prompt: str = ""
    depends_on: List[str] = field(default_factory=list)
    status: TaskStatus = TaskStatus.PENDING
    result: str = ""
    error: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "run_id": self.run_id,
            "agent_name": self.agent_name,
            "role": self.role,
            "prompt": self.prompt,
            "depends_on": self.depends_on,
            "status": self.status.value,
            "result": self.result,
            "error": self.error,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SwarmTask":
        cleaned = {}
        for k, v in d.items():
            if k not in cls.__dataclass_fields__:
                continue
            if k == "status" and isinstance(v, str):
                cleaned[k] = TaskStatus(v)
            else:
                cleaned[k] = v
        return cls(**cleaned)


@dataclass
class SwarmRun:
    run_id: str = field(default_factory=_new_id)
    preset_name: str = ""
    status: RunStatus = RunStatus.PENDING
    tasks: List[SwarmTask] = field(default_factory=list)
    user_vars: Dict[str, str] = field(default_factory=dict)
    final_report: str = ""
    error: Optional[str] = None
    created_at: str = field(default_factory=_utc_now_iso)
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "preset_name": self.preset_name,
            "status": self.status.value,
            "tasks": [t.to_dict() for t in self.tasks],
            "user_vars": self.user_vars,
            "final_report": self.final_report,
            "error": self.error,
            "created_at": self.created_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SwarmRun":
        tasks = [SwarmTask.from_dict(t) for t in d.get("tasks", [])]
        cleaned = {}
        for k, v in d.items():
            if k in ("tasks",):
                continue
            if k not in cls.__dataclass_fields__:
                continue
            if k == "status" and isinstance(v, str):
                cleaned[k] = RunStatus(v)
            else:
                cleaned[k] = v
        cleaned["tasks"] = tasks
        return cls(**cleaned)

    def get_ready_tasks(self) -> List[SwarmTask]:
        completed_ids = {t.task_id for t in self.tasks if t.status == TaskStatus.COMPLETED}
        return [
            t for t in self.tasks
            if t.status == TaskStatus.PENDING
            and all(dep in completed_ids for dep in t.depends_on)
        ]

    def all_done(self) -> bool:
        if not self.tasks:
            return True
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED) for t in self.tasks)
