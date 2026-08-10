import pytest

from vinu_agent.config import _load_orchestrator_llm_config, load_config


_ORCH_KEYS = (
    "VINU_ORCHESTRATOR_LLM_PROVIDER",
    "VINU_ORCHESTRATOR_LLM_MODEL",
    "VINU_ORCHESTRATOR_LLM_BASE_URL",
    "VINU_ORCHESTRATOR_LLM_API_KEY",
    "VINU_ORCHESTRATOR_LLM_TIMEOUT",
    "VINU_ORCHESTRATOR_LLM_CONTEXT_WINDOW",
)


@pytest.fixture(autouse=True)
def _clear_orchestrator_llm_env(monkeypatch):
    for key in _ORCH_KEYS:
        monkeypatch.delenv(key, raising=False)


class TestLoadOrchestratorLlmConfig:
    def test_returns_none_when_nothing_set(self) -> None:
        assert _load_orchestrator_llm_config() is None

    def test_builds_config_when_provider_set(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_PROVIDER", "openai")
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_MODEL", "gpt-4o")
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_API_KEY", "sk-test")
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_BASE_URL", "https://api.openai.com/v1")

        cfg = _load_orchestrator_llm_config()

        assert cfg is not None
        assert cfg.provider == "openai"
        assert cfg.model_name == "gpt-4o"
        assert cfg.api_key == "sk-test"
        assert cfg.base_url == "https://api.openai.com/v1"

    def test_builds_config_when_only_model_set(self, monkeypatch) -> None:
        """Even a single VINU_ORCHESTRATOR_LLM_* var is enough to opt in --
        the rest fall back to LLMConfig's own plain defaults, not the
        shared VINU_LLM_* values (mixing a shared local model name with a
        different provider would be silently wrong)."""
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_MODEL", "gpt-4o-mini")
        cfg = _load_orchestrator_llm_config()
        assert cfg is not None
        assert cfg.model_name == "gpt-4o-mini"
        assert cfg.provider == "openai"  # LLMConfig's own default, not derived from VINU_LLM_PROVIDER
        assert cfg.api_key == ""

    def test_timeout_and_context_window_are_ints(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_PROVIDER", "openai")
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_TIMEOUT", "60")
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_CONTEXT_WINDOW", "128000")
        cfg = _load_orchestrator_llm_config()
        assert cfg.timeout == 60
        assert cfg.context_window == 128000


class TestLoadConfigOrchestratorLlm:
    def test_load_config_orchestrator_llm_defaults_to_none(self) -> None:
        config = load_config()
        assert config.orchestrator_llm is None

    def test_load_config_picks_up_orchestrator_llm_env(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_PROVIDER", "anthropic")
        monkeypatch.setenv("VINU_ORCHESTRATOR_LLM_MODEL", "claude-opus")
        config = load_config()
        assert config.orchestrator_llm is not None
        assert config.orchestrator_llm.provider == "anthropic"
        assert config.orchestrator_llm.model_name == "claude-opus"
        # Teams/specialists' LLMConfig is untouched by the orchestrator override.
        assert config.llm.provider != "anthropic" or config.llm is not config.orchestrator_llm
