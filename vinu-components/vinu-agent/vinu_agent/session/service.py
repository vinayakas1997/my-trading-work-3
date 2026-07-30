import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from ..agent.context import ContextBuilder
from .events import EventBus, SSEEvent
from .models import Attempt, Message, Session
from .store import SessionStore


class SessionService:
    _AGENT_EXECUTOR = ThreadPoolExecutor(max_workers=4)

    def __init__(
        self,
        store: SessionStore,
        event_bus: EventBus,
        llm: Any = None,
        skills_loader: Any = None,
        persistent_memory: Any = None,
        unified_memory: Any = None,
        services_config: Optional[dict] = None,
    ) -> None:
        self.store = store
        self.event_bus = event_bus
        self._llm = llm
        self._skills_loader = skills_loader
        self._persistent_memory = persistent_memory
        self._unified_memory = unified_memory
        self._services_config = services_config or {}
        self._active_loops: Dict[str, Any] = {}
        self._context_builder: Optional[ContextBuilder] = None

    async def create_session(self, title: str = "", config: Optional[dict] = None) -> Session:
        session = Session(title=title, config=config or {})
        self.store.create_session(session)
        self.event_bus.publish(SSEEvent(
            event_type="session.created",
            data=session.to_dict(),
            session_id=session.session_id,
        ))
        return session

    async def send_message(
        self, session_id: str, content: str, role: str = "user"
    ) -> Dict:
        session = self.store.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        msg = Message(
            session_id=session_id,
            role=role,
            content=content,
        )
        self.store.append_message(session_id, msg)

        self.event_bus.publish(SSEEvent(
            event_type="message.received",
            data=msg.to_dict(),
            session_id=session_id,
        ))

        if role != "user":
            return {"message_id": msg.message_id}

        attempt = Attempt(
            session_id=session_id,
            prompt=content,
        )
        self.store.save_attempt(session_id, attempt)

        self.event_bus.publish(SSEEvent(
            event_type="attempt.created",
            data=attempt.to_dict(),
            session_id=session_id,
        ))

        asyncio.create_task(self._run_attempt(session_id, attempt.attempt_id))

        return {"message_id": msg.message_id, "attempt_id": attempt.attempt_id}

    async def _run_attempt(self, session_id: str, attempt_id: str) -> None:
        attempt = self.store.get_attempt(session_id, attempt_id)
        attempt.mark_running()

        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self._AGENT_EXECUTOR,
                self._run_with_agent,
                session_id,
                attempt,
            )

            assistant_msg = Message(
                session_id=session_id,
                role="assistant",
                content=result.get("content", ""),
                linked_attempt_id=attempt_id,
            )
            self.store.append_message(session_id, assistant_msg)

            attempt.mark_completed(summary=result.get("content", "")[:500])
            self.store.save_attempt(session_id, attempt)

            self.event_bus.publish(SSEEvent(
                event_type="attempt.completed",
                data=attempt.to_dict(),
                session_id=session_id,
            ))

        except Exception as exc:
            attempt.mark_failed(error=str(exc))
            self.store.save_attempt(session_id, attempt)

            self.event_bus.publish(SSEEvent(
                event_type="attempt.failed",
                data=attempt.to_dict(),
                session_id=session_id,
            ))

    def _run_with_agent(self, session_id: str, attempt: Attempt) -> Dict:
        from ..agent.loop import AgentLoop
        from ..agent.workflow import WorkflowTracker
        from ..tools import build_registry

        workflow_tracker = WorkflowTracker()

        registry = build_registry(
            session_id=session_id,
            services_config=self._services_config,
            persistent_memory=self._persistent_memory,
            unified_memory=self._unified_memory,
            skills_loader=self._skills_loader,
            session_service=self,
            workflow_tracker=workflow_tracker,
        )

        context_builder = ContextBuilder(
            registry=registry,
            memory=None,
            skills_loader=self._skills_loader,
            persistent_memory=self._persistent_memory,
            unified_memory=self._unified_memory,
        )
        self._context_builder = context_builder

        def event_callback(event_type: str, data: dict):
            self.event_bus.publish(SSEEvent(
                event_type=event_type,
                data=data,
                session_id=session_id,
            ))

        agent_loop = AgentLoop(
            registry=registry,
            llm=self._llm,
            event_callback=event_callback,
            max_iterations=50,
            persistent_memory=self._persistent_memory,
        )
        agent_loop._workflow_tracker = workflow_tracker
        self._active_loops[session_id] = agent_loop

        try:
            messages = self.store.get_messages(session_id, limit=50)
            history = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            user_msg = history[-1]["content"] if history else ""
            messages_with_system = context_builder.build_messages(
                history[:-1], user_msg
            )
            result = agent_loop.run(
                messages=messages_with_system,
                session_id=session_id,
            )
            return result
        finally:
            self._active_loops.pop(session_id, None)

    def cancel_current(self, session_id: str) -> bool:
        loop = self._active_loops.get(session_id)
        if loop:
            loop.cancel()
            return True
        return False

    def search(self, query: str) -> list:
        from .search import FTSSearch
        searcher = FTSSearch(
            Path(self.store.base_dir) / "search.db"
        )
        return searcher.search(query)
