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
        orchestrator_llm: Any = None,
        skills_loader: Any = None,
        persistent_memory: Any = None,
        unified_memory: Any = None,
        facts_registry: Any = None,
        services_config: Optional[dict] = None,
        teams_dir: str = "",
        orchestrator_dir: str = "",
        run_store: Any = None,
        llm_call_store: Any = None,
        strategy_store: Any = None,
        ticker_summary_store: Any = None,
        ticker_ledger_store: Any = None,
    ) -> None:
        self.store = store
        self.event_bus = event_bus
        self._llm = llm
        # None means "share `llm` with teams/specialists" -- see
        # config.py::_load_orchestrator_llm_config and
        # New-talk-agents/implementation/00-status.md.
        self._orchestrator_llm = orchestrator_llm if orchestrator_llm is not None else llm
        self._skills_loader = skills_loader
        self._persistent_memory = persistent_memory
        self._unified_memory = unified_memory
        self._facts_registry = facts_registry
        self._services_config = services_config or {}
        self._teams_dir = teams_dir
        self._run_store = run_store
        self._llm_call_store = llm_call_store
        self._strategy_store = strategy_store
        self._ticker_summary_store = ticker_summary_store
        self._ticker_ledger_store = ticker_ledger_store
        self._orchestrator_prompt = self._load_orchestrator_prompt(orchestrator_dir)
        self._active_loops: Dict[str, Any] = {}
        self._context_builder: Optional[ContextBuilder] = None

    @staticmethod
    def _load_orchestrator_prompt(orchestrator_dir: str) -> str:
        if not orchestrator_dir:
            return ""
        path = Path(orchestrator_dir) / "ORCHESTRATOR.md"
        if not path.exists():
            return ""
        from ..agent.frontmatter import parse_frontmatter
        _meta, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        return body

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
        self, session_id: str, content: str, role: str = "user", as_of: str | None = None
    ) -> Dict:
        session = self.store.get_session(session_id)
        if not session:
            raise ValueError(f"Session {session_id} not found")

        if as_of is not None:
            session.config["as_of"] = as_of
            self.store.update_session(session)

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

            trace = result.get("trace") or []
            attempt.react_trace = [
                {
                    "role": step.get("role"),
                    "content": step.get("content"),
                    "tool_calls": step.get("tool_calls"),
                }
                for step in trace
            ]

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
        import os

        from ..agent.llm import wrap_with_logging
        from ..agent.loop import AgentLoop
        from ..agent.workflow import WorkflowTracker
        from ..audit.freshness import FreshnessChecker
        from ..audit.ground_truth import GroundTruthInjector, _build_broker, _get_held_symbols
        from ..audit.research_digest import ResearchDigestReader
        from ..broker.debrief import PositionCloseDetector
        from ..tools import build_registry

        session = self.store.get_session(session_id)
        as_of = (session.config or {}).get("as_of") if session else None

        workflow_tracker = WorkflowTracker()

        def event_callback(event_type: str, data: dict):
            self.event_bus.publish(SSEEvent(
                event_type=event_type,
                data=data,
                session_id=session_id,
            ))

        registry = build_registry(
            session_id=session_id,
            services_config=self._services_config,
            persistent_memory=self._persistent_memory,
            unified_memory=self._unified_memory,
            skills_loader=self._skills_loader,
            session_service=self,
            workflow_tracker=workflow_tracker,
            as_of=as_of,
            llm=self._llm,
            teams_dir=self._teams_dir,
            run_store=self._run_store,
            llm_call_store=self._llm_call_store,
            strategy_store=self._strategy_store,
            ticker_summary_store=self._ticker_summary_store,
            ticker_ledger_store=self._ticker_ledger_store,
            event_callback=event_callback,
        )

        held_symbols = _get_held_symbols(as_of, session_id)
        ground_truth_injector = GroundTruthInjector(
            registry=registry, as_of=as_of,
            services_config=self._services_config,
        )

        # Freshness checking compares a value's `analysis_at` against real
        # wall-clock time — meaningless in replay mode, where "now" is a
        # simulated past date, so this only runs live.
        freshness_checker = FreshnessChecker(services_config=self._services_config) if as_of is None else None

        data_root = os.environ.get("VINU_AGENT_DATA_ROOT", "/data")
        digest_state_file = f"{session_id}.json" if as_of else "live.json"
        research_digest_reader = ResearchDigestReader(
            services_config=self._services_config,
            state_path=os.path.join(data_root, "research_digest_state", digest_state_file),
        )

        try:
            broker = _build_broker(as_of, session_id)
            if broker.is_configured():
                state_path = os.path.join(data_root, "debrief_state", digest_state_file)
                debrief_detector = PositionCloseDetector(
                    registry=registry, state_path=state_path,
                    services_config=self._services_config,
                    ticker_ledger_store=self._ticker_ledger_store,
                )
                debrief_detector.check_and_debrief(broker, session_id=session_id)
        except Exception:
            pass

        context_builder = ContextBuilder(
            registry=registry,
            memory=None,
            skills_loader=self._skills_loader,
            persistent_memory=self._persistent_memory,
            unified_memory=self._unified_memory,
            as_of=as_of,
            ground_truth_injector=ground_truth_injector,
            held_symbols=held_symbols,
            facts_registry=self._facts_registry,
            freshness_checker=freshness_checker,
            research_digest_reader=research_digest_reader,
            orchestrator_prompt=self._orchestrator_prompt,
        )
        self._context_builder = context_builder

        orchestrator_llm = wrap_with_logging(
            self._orchestrator_llm, self._llm_call_store,
            service="vinu-agent", tier="orchestrator", session_id=session_id,
        )
        agent_loop = AgentLoop(
            registry=registry,
            llm=orchestrator_llm,
            event_callback=event_callback,
            max_iterations=50,
            persistent_memory=self._persistent_memory,
            data_root=data_root,
            service_name="vinu-agent",
        )
        agent_loop._workflow_tracker = workflow_tracker
        agent_loop._ground_truth_system_msg = context_builder.last_ground_truth_msg
        agent_loop._facts_system_msg = context_builder.last_facts_msg
        agent_loop._freshness_system_msg = context_builder.last_freshness_msg
        agent_loop._research_digest_system_msg = context_builder.last_research_digest_msg
        self._active_loops[session_id] = agent_loop

        try:
            messages = self.store.get_messages(session_id, limit=50)
            history = [
                {"role": m.role, "content": m.content}
                for m in messages
            ]
            user_msg = history[-1]["content"] if history else ""
            messages_with_system = context_builder.build_messages(
                history[:-1], user_msg, session_id=session_id,
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
