import os

from vinu_lib.config import ServiceConfig, from_env


def test_service_config_defaults():
    cfg = ServiceConfig()
    assert cfg.host == "127.0.0.1"
    assert cfg.port == 8080
    assert cfg.log_level == "INFO"
    assert cfg.env == "development"


def test_service_config_custom():
    cfg = ServiceConfig(host="0.0.0.0", port=9090, log_level="DEBUG", env="production")
    assert cfg.host == "0.0.0.0"
    assert cfg.port == 9090
    assert cfg.log_level == "DEBUG"
    assert cfg.env == "production"


def test_from_env_defaults():
    cfg = from_env("TEST_SVC", {"host": "1.2.3.4", "port": 1234})
    assert cfg.host == "1.2.3.4"
    assert cfg.port == 1234


def test_from_env_with_env_vars(monkeypatch):
    monkeypatch.setenv("TEST_SVC_HOST", "10.0.0.1")
    monkeypatch.setenv("TEST_SVC_PORT", "5678")
    monkeypatch.setenv("TEST_SVC_LOG_LEVEL", "debug")
    cfg = from_env("TEST_SVC", {"host": "1.2.3.4", "port": 1234})
    assert cfg.host == "10.0.0.1"
    assert cfg.port == 5678
    assert cfg.log_level == "DEBUG"
