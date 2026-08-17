import os

import pytest

from vinu_infra.secrets_loader import load_secret, require_secret, secrets_dir


def _write_secret(tmp_path, name, value):
    (tmp_path / name).write_text(value)
    return str(tmp_path)


class TestLoadSecretResolution:
    def test_secret_file_wins_over_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", _write_secret(tmp_path, "vinu_api_key", "from-file\n"))
        monkeypatch.setenv("VINU_API_KEY", "from-env")
        assert load_secret("vinu_api_key", "VINU_API_KEY") == "from-file"

    def test_strips_whitespace_and_newline(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", _write_secret(tmp_path, "alpaca_api_key", "  key-value  \n"))
        assert load_secret("alpaca_api_key") == "key-value"

    def test_empty_secret_file_falls_back_to_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", _write_secret(tmp_path, "vinu_api_key", "   \n"))
        monkeypatch.setenv("VINU_API_KEY", "from-env")
        assert load_secret("vinu_api_key", "VINU_API_KEY") == "from-env"

    def test_falls_back_to_env_when_no_secret_file(self, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", "/nonexistent-secrets-dir")
        monkeypatch.setenv("VINU_API_KEY", "from-env")
        assert load_secret("vinu_api_key", "VINU_API_KEY") == "from-env"

    def test_returns_none_when_neither_exists(self, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", "/nonexistent-secrets-dir")
        monkeypatch.delenv("VINU_API_KEY", raising=False)
        assert load_secret("vinu_api_key", "VINU_API_KEY") is None

    def test_secret_file_path_never_read_through_env(self, tmp_path, monkeypatch):
        # Ensure an empty env var cannot defeat a populated secret file.
        monkeypatch.setenv("VINU_SECRETS_DIR", _write_secret(tmp_path, "k", "file-value"))
        monkeypatch.delenv("VINU_API_KEY", raising=False)
        assert load_secret("k") == "file-value"


class TestRequireSecret:
    def test_returns_value_when_present(self, tmp_path, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", _write_secret(tmp_path, "vinu_api_key", "abc"))
        assert require_secret("vinu_api_key", "VINU_API_KEY") == "abc"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", "/nonexistent")
        monkeypatch.delenv("VINU_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            require_secret("vinu_api_key", "VINU_API_KEY")


class TestSecretsDir:
    def test_default_is_run_secrets(self, monkeypatch):
        monkeypatch.delenv("VINU_SECRETS_DIR", raising=False)
        assert os.fspath(secrets_dir()) == "/run/secrets"

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("VINU_SECRETS_DIR", "/tmp/custom-secrets")
        assert os.fspath(secrets_dir()) == "/tmp/custom-secrets"
