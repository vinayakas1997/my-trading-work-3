from __future__ import annotations

from vinu_reflection.config import load_config


class TestBrainSynthesisConfig:
    def test_defaults_to_disabled(self, monkeypatch) -> None:
        monkeypatch.delenv("VINU_REFLECTION_BRAIN_SYNTHESIS_ENABLED", raising=False)
        assert load_config().brain_synthesis_enabled is False

    def test_picks_up_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_REFLECTION_BRAIN_SYNTHESIS_ENABLED", "true")
        assert load_config().brain_synthesis_enabled is True

    def test_interval_defaults_to_an_hour(self, monkeypatch) -> None:
        monkeypatch.delenv("VINU_REFLECTION_BRAIN_SYNTHESIS_INTERVAL_SEC", raising=False)
        assert load_config().brain_synthesis_worker_interval_sec == 3600

    def test_interval_picks_up_env_var(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_REFLECTION_BRAIN_SYNTHESIS_INTERVAL_SEC", "60")
        assert load_config().brain_synthesis_worker_interval_sec == 60


class TestServeConfig:
    """Step 9: host/port for the new read-only HTTP surface."""

    def test_defaults(self, monkeypatch) -> None:
        monkeypatch.delenv("VINU_REFLECTION_HOST", raising=False)
        monkeypatch.delenv("VINU_REFLECTION_PORT", raising=False)
        config = load_config()
        assert config.host == "127.0.0.1"
        assert config.port == 8092

    def test_picks_up_env_vars(self, monkeypatch) -> None:
        monkeypatch.setenv("VINU_REFLECTION_HOST", "0.0.0.0")
        monkeypatch.setenv("VINU_REFLECTION_PORT", "9000")
        config = load_config()
        assert config.host == "0.0.0.0"
        assert config.port == 9000
