import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SessionStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class AttemptStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_USER = "waiting_user"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


def _utc_now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


@dataclass
class Session:
    session_id: str = field(default_factory=_new_id)
    title: str = ""
    status: SessionStatus = SessionStatus.ACTIVE
    created_at: str = field(default_factory=_utc_now_iso)
    updated_at: str = field(default_factory=_utc_now_iso)
    last_attempt_id: Optional[str] = None
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "title": self.title,
            "status": self.status.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_attempt_id": self.last_attempt_id,
            "config": self.config,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Session":
        return cls(
            session_id=d["session_id"],
            title=d.get("title", ""),
            status=SessionStatus(d.get("status", "active")),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
            last_attempt_id=d.get("last_attempt_id"),
            config=d.get("config", {}),
        )


@dataclass
class Message:
    message_id: str = field(default_factory=_new_id)
    session_id: str = ""
    role: str = "user"
    content: str = ""
    created_at: str = field(default_factory=_utc_now_iso)
    linked_attempt_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "message_id": self.message_id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "created_at": self.created_at,
            "linked_attempt_id": self.linked_attempt_id,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Message":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Attempt:
    attempt_id: str = field(default_factory=_new_id)
    session_id: str = ""
    parent_attempt_id: Optional[str] = None
    status: AttemptStatus = AttemptStatus.PENDING
    prompt: str = ""
    run_dir: Optional[str] = None
    summary: Optional[str] = None
    react_trace: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    metrics: Optional[Dict[str, Any]] = None
    created_at: str = field(default_factory=_utc_now_iso)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def mark_running(self) -> None:
        self.status = AttemptStatus.RUNNING
        self.started_at = _utc_now_iso()

    def mark_completed(self, summary: str = "") -> None:
        self.status = AttemptStatus.COMPLETED
        self.summary = summary
        self.completed_at = _utc_now_iso()

    def mark_failed(self, error: str) -> None:
        self.status = AttemptStatus.FAILED
        self.error = error
        self.completed_at = _utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "attempt_id": self.attempt_id,
            "session_id": self.session_id,
            "parent_attempt_id": self.parent_attempt_id,
            "status": self.status.value,
            "prompt": self.prompt,
            "run_dir": self.run_dir,
            "summary": self.summary,
            "react_trace": self.react_trace,
            "error": self.error,
            "metrics": self.metrics,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Attempt":
        cleaned = {}
        for k, v in d.items():
            if k not in cls.__dataclass_fields__:
                continue
            if k == "status" and isinstance(v, str):
                cleaned[k] = AttemptStatus(v)
            else:
                cleaned[k] = v
        return cls(**cleaned)
