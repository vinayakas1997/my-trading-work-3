import asyncio
import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional


@dataclass
class SSEEvent:
    event_id: Optional[str] = field(default_factory=lambda: uuid.uuid4().hex[:16])
    event_type: str = "message"
    data: Dict[str, Any] = field(default_factory=dict)
    session_id: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_sse(self) -> str:
        payload = json.dumps(self.data, default=str)
        return f"id: {self.event_id}\nevent: {self.event_type}\ndata: {payload}\n\n"


class EventBus:
    def __init__(self, max_buffer_size: int = 500, queue_timeout: float = 30.0) -> None:
        self._lock = threading.Lock()
        self._buffer: list = []
        self._max_buffer_size = max_buffer_size
        self._queue_timeout = queue_timeout
        self._subscribers: Dict[str, asyncio.Queue] = {}
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def publish(self, event: SSEEvent) -> None:
        with self._lock:
            self._buffer.append(event)
            if len(self._buffer) > self._max_buffer_size:
                self._buffer = self._buffer[-self._max_buffer_size:]
            for queue in self._subscribers.values():
                if self._loop:
                    self._loop.call_soon_threadsafe(queue.put_nowait, event)

    async def subscribe(
        self, session_id: str, last_event_id: Optional[str] = None
    ) -> AsyncGenerator[SSEEvent, None]:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        with self._lock:
            self._subscribers[session_id] = queue

        if last_event_id:
            for event in self._replay(session_id, last_event_id):
                yield event

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=self._queue_timeout)
                    yield event
                except asyncio.TimeoutError:
                    yield SSEEvent(event_type="heartbeat", data={})
        finally:
            with self._lock:
                self._subscribers.pop(session_id, None)

    def _replay(self, session_id: str, last_event_id: str) -> list:
        found = False
        result = []
        for event in self._buffer:
            if event.session_id != session_id:
                continue
            if found:
                result.append(event)
            if event.event_id == last_event_id:
                found = True
        return result
