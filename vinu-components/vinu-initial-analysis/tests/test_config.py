from __future__ import annotations

from vinu_initial_analysis.config import DEFAULT_MIN_OBSERVATIONS, get_angle_setting


def test_get_angle_setting_falls_back_to_default_when_env_unset(monkeypatch):
    monkeypatch.delenv("VINU_TESTANGLE_MIN_OBSERVATIONS", raising=False)
    assert get_angle_setting("testangle", "min_observations", DEFAULT_MIN_OBSERVATIONS) == DEFAULT_MIN_OBSERVATIONS


def test_get_angle_setting_falls_back_to_a_special_default_not_just_the_shared_one():
    assert get_angle_setting("chronos", "min_observations", 512) == 512


def test_get_angle_setting_reads_the_env_override(monkeypatch):
    monkeypatch.setenv("VINU_TESTANGLE_MIN_OBSERVATIONS", "250")
    assert get_angle_setting("testangle", "min_observations", DEFAULT_MIN_OBSERVATIONS) == 250


def test_get_angle_setting_ignores_blank_env_value(monkeypatch):
    monkeypatch.setenv("VINU_TESTANGLE_MIN_OBSERVATIONS", "  ")
    assert get_angle_setting("testangle", "min_observations", DEFAULT_MIN_OBSERVATIONS) == DEFAULT_MIN_OBSERVATIONS


def test_get_angle_setting_env_var_name_is_angle_and_setting_specific(monkeypatch):
    # Overriding one angle's setting must never leak into another angle's,
    # or into a differently-named setting on the same angle.
    monkeypatch.setenv("VINU_LSTM_MIN_OBSERVATIONS", "250")
    assert get_angle_setting("lstm", "min_observations", DEFAULT_MIN_OBSERVATIONS) == 250
    assert get_angle_setting("patchtst", "min_observations", DEFAULT_MIN_OBSERVATIONS) == DEFAULT_MIN_OBSERVATIONS
    assert get_angle_setting("lstm", "max_context", 1024) == 1024


def test_get_angle_setting_uppercases_angle_and_setting_name(monkeypatch):
    monkeypatch.setenv("VINU_MYANGLE_SOME_SETTING", "77")
    assert get_angle_setting("MyAngle", "Some_Setting", 1) == 77
