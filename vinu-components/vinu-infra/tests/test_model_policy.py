from __future__ import annotations

import importlib
import os

import pytest

from vinu_infra import model_policy as model_policy_module


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """model_policy.MODELS_ENABLED is a boot-only module-level constant
    (read once at import, per its own docstring) -- tests reload the
    module after setting env so each test observes a fresh import, the
    same way a real process would after a real restart."""
    monkeypatch.delenv("VINU_MODELS_ENABLED", raising=False)
    for key in list(os.environ):
        if key.startswith("VINU_") and key.endswith("_CHECKPOINT"):
            monkeypatch.delenv(key, raising=False)
    importlib.reload(model_policy_module)
    yield
    importlib.reload(model_policy_module)


def test_models_enabled_defaults_true():
    assert model_policy_module.models_enabled() is True


def test_models_enabled_false_via_env(monkeypatch):
    monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
    importlib.reload(model_policy_module)
    assert model_policy_module.models_enabled() is False


@pytest.mark.parametrize("raw", ["0", "no", "off", "False", ""])
def test_models_enabled_falsy_variants(monkeypatch, raw):
    monkeypatch.setenv("VINU_MODELS_ENABLED", raw)
    importlib.reload(model_policy_module)
    # blank string is treated as unset -> default True; every other falsy
    # spelling in the list disables it.
    expected = raw.strip() == ""
    assert model_policy_module.models_enabled() is expected


def test_get_model_checkpoint_default_when_unset():
    assert model_policy_module.get_model_checkpoint("chronos", "amazon/chronos-t5-large") == "amazon/chronos-t5-large"


def test_get_model_checkpoint_override(monkeypatch):
    monkeypatch.setenv("VINU_CHRONOS_CHECKPOINT", "chronos-t5-tiny")
    assert model_policy_module.get_model_checkpoint("chronos", "amazon/chronos-t5-large") == "chronos-t5-tiny"


def test_policy_version_stable_for_same_env(monkeypatch):
    monkeypatch.setenv("VINU_CHRONOS_CHECKPOINT", "chronos-t5-tiny")
    importlib.reload(model_policy_module)
    v1 = model_policy_module.policy_version()
    v2 = model_policy_module.policy_version()
    assert v1 == v2


def test_policy_version_changes_when_models_toggled(monkeypatch):
    importlib.reload(model_policy_module)
    v_enabled = model_policy_module.policy_version()

    monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
    importlib.reload(model_policy_module)
    v_disabled = model_policy_module.policy_version()

    assert v_enabled != v_disabled


def test_policy_version_changes_when_checkpoint_override_added(monkeypatch):
    importlib.reload(model_policy_module)
    v_before = model_policy_module.policy_version()

    monkeypatch.setenv("VINU_CHRONOS_CHECKPOINT", "chronos-t5-tiny")
    importlib.reload(model_policy_module)
    v_after = model_policy_module.policy_version()

    assert v_before != v_after
