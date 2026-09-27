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
