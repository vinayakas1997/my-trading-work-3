from __future__ import annotations

import os
from pathlib import Path

import pytest

from vinu_research.config import (
    ResearchConfig,
    _reset_env_for_testing,
    load_config,
)


@pytest.fixture(autouse=True)
def reset_env():
    _reset_env_for_testing()
    yield
    _reset_env_for_testing()


def test_load_config_defaults(monkeypatch):
    # This test asserts against the code's built-in defaults, not whatever a
    # developer's local .env happens to contain (e.g. docker-compose service
    # hostnames) — force_reload alone still re-reads the real .env file from
    # disk, so load_dotenv itself must be neutralized here to get a genuinely
    # clean environment regardless of what's on this machine.
    monkeypatch.setattr("vinu_research.config.load_dotenv", lambda *a, **k: None)
    cfg = load_config(force_reload=True)
    assert cfg.features_api_url == "http://127.0.0.1:8082"
    assert cfg.simulator_api_url == "http://127.0.0.1:8085"
    assert cfg.correlation_api_url == "http://127.0.0.1:8083"
    assert cfg.max_iterations == 5
    assert cfg.improvement_threshold == 0.05
    assert cfg.initial_capital == 1_000_000.0
    assert cfg.transaction_cost_pct == 0.001
    assert cfg.slippage_pct == 0.0005
    assert cfg.allow_short is True
    assert cfg.max_drawdown_threshold == -0.25
    assert cfg.llm_enabled is False
    assert cfg.llm_base_url == "http://127.0.0.1:11434/v1"
    assert cfg.llm_model == "llama3.2"
    assert cfg.llm_api_key is None
    assert cfg.llm_ttl_sec == 86400
    assert isinstance(cfg.data_root, Path)


def test_load_config_env_overrides(monkeypatch, reset_env):
    monkeypatch.setenv("VINU_FEATURES_API_URL", "http://custom:9999")
    monkeypatch.setenv("VINU_RESEARCH_MAX_ITERATIONS", "10")
    monkeypatch.setenv("VINU_RESEARCH_INITIAL_CAPITAL", "500000.0")
    monkeypatch.setenv("VINU_RESEARCH_ALLOW_SHORT", "false")
    monkeypatch.setenv("VINU_RESEARCH_DATA_ROOT", "/tmp/test_data")
    cfg = load_config(force_reload=True)
    assert cfg.features_api_url == "http://custom:9999"
    assert cfg.max_iterations == 10
    assert cfg.initial_capital == 500000.0
    assert cfg.allow_short is False
    assert cfg.data_root == Path("/tmp/test_data")


def test_research_config_direct_construction():
    cfg = ResearchConfig(max_iterations=3, allow_short=False)
    assert cfg.max_iterations == 3
    assert cfg.allow_short is False


def test_research_config_defaults():
    cfg = ResearchConfig()
    assert cfg.max_iterations == 5
    assert cfg.initial_capital == 1_000_000.0
    assert cfg.transaction_cost_pct == 0.001
    assert cfg.slippage_pct == 0.0005
