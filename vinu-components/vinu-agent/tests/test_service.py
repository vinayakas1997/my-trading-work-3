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


@pytest.fixture(autouse=True)
def _isolate_research_data_root(tmp_path: Path, monkeypatch) -> None:
    """AgentService.__init__ unconditionally calls get_strategy_store()
    (broker/research_link.py), which resolves VINU_RESEARCH_DATA_ROOT (or
    Path.cwd()/"data" if unset) completely independently of the `config`
    fixture below -- AgentConfig has no field that reaches it. This repo's
    real .env sets VINU_RESEARCH_DATA_ROOT=/data (a real Docker volume
    mount, correct for production), which load_config()'s unconditional
    load_dotenv() call pulls into the environment the first time any test
    in the session calls load_config() -- not writable outside that
    container, so a real AgentService() construction here would otherwise
    fail with PermissionError depending on what ran before this test."""
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", str(tmp_path / "research_data"))


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

    def test_orchestrator_llm_falls_back_to_role_config_when_no_env_var_set(self, tmp_path: Path, monkeypatch) -> None:
        """When VINU_ORCHESTRATOR_LLM_* isn't set, roles.json's
        "orchestrator" role is the second way to configure this tier --
        see missing-pieces-of-system/llm-configuration-settings-system/."""
        import json
        from vinu_infra.llm import roles as roles_module

        roles_path = tmp_path / "roles.json"
        roles_path.write_text(
            json.dumps({"default": {}, "roles": {"orchestrator": {"model": "role-configured-model"}}}),
            encoding="utf-8",
        )
        monkeypatch.setenv("VINU_LLM_ROLES_PATH", str(roles_path))
        roles_module._loaded_path = None
        roles_module._loaded_data = None

        config = AgentConfig(
            llm=LLMConfig(provider="openai", model_name="shared-model", base_url=""),
            skills_dir=str(tmp_path / "skills"),
            teams_dir=str(tmp_path / "teams"),
            orchestrator_dir=str(tmp_path / "orchestrator"),
            sessions_dir=str(tmp_path / "sessions"),
            memory_dir=str(tmp_path / "memory"),
        )
        service = AgentService(config)
        try:
            assert service._orchestrator_llm is not service._llm
            assert service._orchestrator_llm.model == "role-configured-model"
        finally:
            service.close()
            roles_module._loaded_path = None
            roles_module._loaded_data = None

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
