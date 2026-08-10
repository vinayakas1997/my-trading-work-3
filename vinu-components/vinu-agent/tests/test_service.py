"""Tests that actually construct AgentService end-to-end.

Regression motivation: SessionService(orchestrator_llm=...) was called
from AgentService.__init__ for a while before SessionService.__init__
actually accepted that keyword argument -- a TypeError that 363 passing
tests never caught, because nothing anywhere constructs a real
AgentService. This file exists specifically to close that gap.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from vinu_agent.config import AgentConfig, LLMConfig
from vinu_agent.service import AgentService


@pytest.fixture
def config(tmp_path: Path) -> AgentConfig:
    return AgentConfig(
        llm=LLMConfig(provider="openai", model_name="test-model", base_url="", api_key=""),
        skills_dir=str(tmp_path / "skills"),
        teams_dir=str(tmp_path / "teams"),
        orchestrator_dir=str(tmp_path / "orchestrator"),
        sessions_dir=str(tmp_path / "sessions"),
        memory_dir=str(tmp_path / "memory"),
    )


class TestAgentServiceConstruction:
    def test_constructs_without_error(self, config: AgentConfig) -> None:
        service = AgentService(config)
        try:
            assert service.session_service is not None
        finally:
            service.close()

    def test_orchestrator_llm_defaults_to_shared_llm(self, config: AgentConfig) -> None:
        service = AgentService(config)
        try:
            assert service._orchestrator_llm is service._llm
            assert service.session_service._orchestrator_llm is service._llm
        finally:
            service.close()

    def test_orchestrator_llm_is_distinct_when_configured(self, tmp_path: Path) -> None:
        config = AgentConfig(
            llm=LLMConfig(provider="openai", model_name="shared-model", base_url=""),
            orchestrator_llm=LLMConfig(provider="openai", model_name="orchestrator-model", base_url=""),
            skills_dir=str(tmp_path / "skills"),
            teams_dir=str(tmp_path / "teams"),
            orchestrator_dir=str(tmp_path / "orchestrator"),
            sessions_dir=str(tmp_path / "sessions"),
            memory_dir=str(tmp_path / "memory"),
        )
        service = AgentService(config)
        try:
            assert service._orchestrator_llm is not service._llm
            assert service._orchestrator_llm.model == "orchestrator-model"
            assert service._llm.model == "shared-model"
        finally:
            service.close()

    def test_get_status_does_not_raise(self, config: AgentConfig) -> None:
        service = AgentService(config)
        try:
            status = service.get_status()
            assert status["active_sessions"] == 0
        finally:
            service.close()

    def test_close_is_idempotent_safe_and_closes_llm_call_store(self, config: AgentConfig) -> None:
        service = AgentService(config)
        service.close()
        # A second close() must not raise (mirrors the other stores' close()
        # semantics already relied on elsewhere in this codebase).
        service.close()
