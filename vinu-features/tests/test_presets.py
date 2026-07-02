"""Tests for preset registry."""

from vinu_features.presets.registry import get_preset, list_presets, resolve_features


def test_list_presets():
    names = {p.name for p in list_presets()}
    assert "swing_basic" in names


def test_resolve_from_preset():
    feats = resolve_features(preset="basic_ta", features=[])
    assert "rsi_14" in feats


def test_resolve_explicit_features():
    feats = resolve_features(preset=None, features=["sma_100", "rsi_14"])
    assert feats == ["sma_100", "rsi_14"]


def test_get_preset_unknown():
    try:
        get_preset("nope")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "nope" in str(exc)
