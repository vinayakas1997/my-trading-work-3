from pathlib import Path
from typing import Any, Optional

from .agent.context import ContextBuilder
from .agent.llm import create_llm, create_llm_from_config
from .agent.skills import SkillsLoader
from .config import AgentConfig, load_config
from .facts import FactsRegistry, seed_if_empty
from .memory.persistent import PersistentMemory
from .memory.unified_store import UnifiedMemoryStore
from .session.events import EventBus
from .session.models import Session
from .session.service import SessionService
from .session.store import SessionStore
from .storage.llm_calls import LlmCallLogStore
from .storage.team_runs import TeamRunStore
from .swarm.models import SwarmRun
from .swarm.runtime import SwarmRuntime
from .swarm.store import SwarmStore
from .tools import build_registry


class AgentService:
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self._config = config or load_config()
        self._llm = create_llm(self._config)
        # Independent LLM client for the orchestrator's own top-level loop
        # -- only built if configured (VINU_ORCHESTRATOR_LLM_*), otherwise
        # the orchestrator transparently shares `self._llm` with teams/
        # specialists, exactly as before this existed.
        self._orchestrator_llm = (
            create_llm_from_config(self._config.orchestrator_llm)
            if self._config.orchestrator_llm is not None
            else self._llm
        )
        self._event_bus = EventBus()
        self._store = SessionStore(
            Path(self._config.sessions_dir)
        )
        self._memory = PersistentMemory(
            Path(self._config.memory_dir)
        )
        data_root = Path(self._config.memory_dir).parent
        self._unified_memory = UnifiedMemoryStore(
            data_root / "unified_memory.db"
        )
        self._facts_registry = FactsRegistry(data_root / "facts_registry.db")
        seed_if_empty(self._facts_registry)
        self._skills_loader = SkillsLoader(
            skills_dir=Path(self._config.skills_dir) if self._config.skills_dir else None,
            user_skills_dir=Path(self._config.user_skills_dir) if self._config.user_skills_dir else None,
        )
        self._team_run_store = TeamRunStore(data_root / "team_runs.db")
        self._llm_call_store = LlmCallLogStore(data_root / "llm_calls.db")
        self._session_service = SessionService(
            store=self._store,
            event_bus=self._event_bus,
            llm=self._llm,
            orchestrator_llm=self._orchestrator_llm,
            skills_loader=self._skills_loader,
            persistent_memory=self._memory,
            unified_memory=self._unified_memory,
            facts_registry=self._facts_registry,
            services_config=self._config.services,
            teams_dir=self._config.teams_dir,
            orchestrator_dir=self._config.orchestrator_dir,
            run_store=self._team_run_store,
            llm_call_store=self._llm_call_store,
        )
        self._swarm_store = SwarmStore(
            Path(self._config.sessions_dir) / ".." / "swarm"
        )
        self._swarm_runtime = SwarmRuntime(
            store=self._swarm_store,
            services_config=self._config.services,
        )

    @property
    def session_service(self) -> SessionService:
        return self._session_service

    @property
    def event_bus(self) -> EventBus:
        return self._event_bus

    @property
    def config(self) -> AgentConfig:
        return self._config

    @property
    def unified_memory(self) -> UnifiedMemoryStore:
        return self._unified_memory

    async def create_session(self, title: str = "", as_of: str | None = None) -> Session:
        config = {"as_of": as_of} if as_of else None
        return await self._session_service.create_session(title=title, config=config)

    async def send_message(self, session_id: str, content: str, as_of: str | None = None) -> dict:
        return await self._session_service.send_message(session_id, content, as_of=as_of)

    def cancel(self, session_id: str) -> bool:
        return self._session_service.cancel_current(session_id)

    def get_status(self) -> dict:
        return {
            "service": "vinu-agent",
            "active_sessions": len(self._session_service._active_loops),
            "skills_loaded": len(self._skills_loader._skills) if self._skills_loader else 0,
            "llm_provider": self._config.llm.provider,
            "llm_model": self._config.llm.model_name,
        }

    @property
    def swarm_runtime(self) -> SwarmRuntime:
        return self._swarm_runtime

    def close(self) -> None:
        if hasattr(self, "_unified_memory"):
            self._unified_memory.close()
        if hasattr(self, "_facts_registry"):
            self._facts_registry.close()
        if hasattr(self, "_team_run_store"):
            self._team_run_store.close()
        if hasattr(self, "_llm_call_store"):
            self._llm_call_store.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
