from pathlib import Path
from typing import Any, Optional

from .agent.context import ContextBuilder
from .agent.llm import create_llm
from .agent.skills import SkillsLoader
from .config import AgentConfig, load_config
from .memory.persistent import PersistentMemory
from .session.events import EventBus
from .session.models import Session
from .session.service import SessionService
from .session.store import SessionStore
from .swarm.models import SwarmRun
from .swarm.runtime import SwarmRuntime
from .swarm.store import SwarmStore
from .tools import build_registry


class AgentService:
    def __init__(self, config: Optional[AgentConfig] = None) -> None:
        self._config = config or load_config()
        self._llm = create_llm(self._config)
        self._event_bus = EventBus()
        self._store = SessionStore(
            Path(self._config.sessions_dir)
        )
        self._memory = PersistentMemory(
            Path(self._config.memory_dir)
        )
        self._skills_loader = SkillsLoader(
            skills_dir=Path(self._config.skills_dir) if self._config.skills_dir else None,
            user_skills_dir=Path(self._config.user_skills_dir) if self._config.user_skills_dir else None,
        )
        self._session_service = SessionService(
            store=self._store,
            event_bus=self._event_bus,
            llm=self._llm,
            skills_loader=self._skills_loader,
            persistent_memory=self._memory,
            services_config=self._config.services,
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

    async def create_session(self, title: str = "") -> Session:
        return await self._session_service.create_session(title=title)

    async def send_message(self, session_id: str, content: str) -> dict:
        return await self._session_service.send_message(session_id, content)

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
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
