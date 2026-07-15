import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Optional


class ProgressStage(str, Enum):
    START = "start"
    LLM_CALL = "llm_call"
    LLM_RESPONSE = "llm_response"
    TOOL_EXECUTING = "tool_executing"
    TOOL_COMPLETED = "tool_completed"
    COMPACTION = "compaction"
    NUDGE = "nudge"
    CANCELLED = "cancelled"
    COMPLETED = "completed"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


@dataclass
class ProgressEvent:
    stage: ProgressStage
    current: int
    total: int
    message: str
    detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "stage": self.stage.value,
            "current": self.current,
            "total": self.total,
            "message": self.message,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


class HeartbeatTimer:
    def __init__(self, interval: float = 5.0, callback: Optional[Callable[[], None]] = None):
        self._interval = interval
        self._callback = callback
        self._timer: Optional[threading.Timer] = None
        self._running = False

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._schedule()

    def stop(self) -> None:
        self._running = False
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _schedule(self) -> None:
        if not self._running:
            return
        self._timer = threading.Timer(self._interval, self._tick)
        self._timer.daemon = True
        self._timer.start()

    def _tick(self) -> None:
        if self._callback:
            try:
                self._callback()
            except Exception:
                pass
        self._schedule()
