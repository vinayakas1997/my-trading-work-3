import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from vinu_infra.llm import roles as roles_module
from vinu_infra.llm.roles import get_llm_config_for_role, has_role_override


@pytest.fixture(autouse=True)
def _isolated_roles_file(monkeypatch, tmp_path):
    """Every test gets its own roles.json path and a cleared module-level
    cache, so tests never see each other's state or the real repo file."""
    roles_path = tmp_path / "roles.json"
    monkeypatch.setenv("VINU_LLM_ROLES_PATH", str(roles_path))
    roles_module._loaded_path = None
    roles_module._loaded_data = None
    yield roles_path
    roles_module._loaded_path = None
    roles_module._loaded_data = None


def _write_roles(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


class TestMissingOrEmptyFile:
    def test_missing_file_falls_back_to_plain_env_defaults(self, monkeypatch):
        monkeypatch.setenv("VINU_LLM_BASE_URL", "http://plain-default/v1")
        monkeypatch.setenv("VINU_LLM_MODEL", "plain-model")
        cfg = get_llm_config_for_role("anything")
        assert cfg.base_url == "http://plain-default/v1"
        assert cfg.model == "plain-model"

    def test_empty_roles_and_default_blocks_is_a_no_op(self, _isolated_roles_file, monkeypatch):
        _write_roles(_isolated_roles_file, {"default": {}, "roles": {}})
        monkeypatch.setenv("VINU_LLM_MODEL", "plain-model")
        cfg = get_llm_config_for_role("summary_agent")
        assert cfg.model == "plain-model"

    def test_unknown_role_falls_back_to_default_block(self, _isolated_roles_file):
        _write_roles(_isolated_roles_file, {"default": {"model": "default-model"}, "roles": {}})
        cfg = get_llm_config_for_role("nonexistent_role")
        assert cfg.model == "default-model"


class TestRoleOverrides:
    def test_role_block_overrides_default_block(self, _isolated_roles_file):
        _write_roles(
            _isolated_roles_file,
            {
                "default": {"model": "default-model", "base_url": "http://default/v1"},
                "roles": {"orchestrator": {"model": "gpt-4o-mini"}},
            },
        )
        cfg = get_llm_config_for_role("orchestrator")
        assert cfg.model == "gpt-4o-mini"
        assert cfg.base_url == "http://default/v1"  # inherited from default, not overridden

    def test_api_key_env_indirection(self, _isolated_roles_file, monkeypatch):
        monkeypatch.setenv("MY_PROVIDER_KEY", "sk-real-key")
        _write_roles(
            _isolated_roles_file,
            {"default": {}, "roles": {"orchestrator": {"api_key_env": "MY_PROVIDER_KEY"}}},
        )
        cfg = get_llm_config_for_role("orchestrator")
        assert cfg.api_key == "sk-real-key"

    def test_per_field_env_override_wins_over_roles_json(self, _isolated_roles_file, monkeypatch):
        _write_roles(_isolated_roles_file, {"default": {}, "roles": {"orchestrator": {"model": "from-json"}}})
        monkeypatch.setenv("VINU_LLM_ROLE_ORCHESTRATOR_MODEL", "from-env")
        cfg = get_llm_config_for_role("orchestrator")
        assert cfg.model == "from-env"

    def test_other_roles_unaffected_by_one_roles_config(self, _isolated_roles_file):
        _write_roles(
            _isolated_roles_file,
            {"default": {}, "roles": {"orchestrator": {"model": "gpt-4o-mini"}}},
        )
        cfg = get_llm_config_for_role("summary_agent")
        assert cfg.model != "gpt-4o-mini"


class TestHasRoleOverride:
    def test_false_when_nothing_configured(self, _isolated_roles_file):
        _write_roles(_isolated_roles_file, {"default": {}, "roles": {}})
        assert has_role_override("orchestrator") is False

    def test_true_when_roles_json_has_a_block(self, _isolated_roles_file):
        _write_roles(_isolated_roles_file, {"default": {}, "roles": {"orchestrator": {"model": "x"}}})
        assert has_role_override("orchestrator") is True

    def test_true_when_only_an_env_override_is_set(self, _isolated_roles_file, monkeypatch):
        _write_roles(_isolated_roles_file, {"default": {}, "roles": {}})
        monkeypatch.setenv("VINU_LLM_ROLE_ORCHESTRATOR_MODEL", "gpt-4o-mini")
        assert has_role_override("orchestrator") is True

    def test_false_for_an_unrelated_role(self, _isolated_roles_file):
        _write_roles(_isolated_roles_file, {"default": {}, "roles": {"orchestrator": {"model": "x"}}})
        assert has_role_override("summary_agent") is False


def test_malformed_json_falls_back_to_empty_not_a_crash(_isolated_roles_file):
    _isolated_roles_file.write_text("{not valid json", encoding="utf-8")
    cfg = get_llm_config_for_role("anything")  # must not raise
    assert cfg is not None
