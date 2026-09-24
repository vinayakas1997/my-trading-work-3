from __future__ import annotations

import importlib

import pytest

from vinu_infra import model_policy as model_policy_module
from vinu_infra import system_manifest as system_manifest_module


def _angle(name: str, category: str, time_formats: list[str] | None = None) -> dict:
    return {
        "name": name,
        "spec": {
            "category": category,
            "time_formats": time_formats if time_formats is not None else ["15min", "1D"],
        },
    }


@pytest.fixture(autouse=True)
def _reload_modules(monkeypatch):
    monkeypatch.delenv("VINU_MODELS_ENABLED", raising=False)
    importlib.reload(model_policy_module)
    importlib.reload(system_manifest_module)
    yield
    importlib.reload(model_policy_module)
    importlib.reload(system_manifest_module)


def _sample_angles() -> list[dict]:
    return [
        _angle("shock_personality", "raw_data"),
        _angle("shock_clustering", "raw_data"),
        _angle("news_price_causality", "news"),
        _angle("chronos", "model"),
        _angle("patchtst", "model"),
        _angle("moirai", "model"),  # tagged model by intent, but permanently excluded
        _angle("moment", "raw_data"),  # mis-tagged on purpose: exclusion must still win
        _angle("lag_llama", "model"),
    ]


def test_resolve_active_angles_excludes_permanently_disabled_regardless_of_tag():
    active = system_manifest_module.resolve_active_angles(_sample_angles())
    active_names = {a["name"] for a in active}
    assert "moirai" not in active_names
    assert "moment" not in active_names
    assert "lag_llama" not in active_names


def test_resolve_active_angles_keeps_models_when_enabled():
    active = system_manifest_module.resolve_active_angles(_sample_angles())
    active_names = {a["name"] for a in active}
    assert "chronos" in active_names
    assert "patchtst" in active_names


def test_resolve_active_angles_drops_models_when_disabled(monkeypatch):
    monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
    importlib.reload(model_policy_module)
    importlib.reload(system_manifest_module)
    active = system_manifest_module.resolve_active_angles(_sample_angles())
    active_names = {a["name"] for a in active}
    assert "chronos" not in active_names
    assert "patchtst" not in active_names
    # raw_data/news untouched by the MODELS switch
    assert "shock_personality" in active_names
    assert "news_price_causality" in active_names


def test_build_manifest_angle_inventory_counts():
    manifest = system_manifest_module.build_manifest(_sample_angles())
    inv = manifest["angle_inventory"]
    assert inv["total"] == 8
    assert set(inv["permanently_disabled"]) == {"moirai", "moment", "lag_llama"}
    # "moment" was mis-tagged raw_data in the fixture on purpose -- inventory
    # counts it under "disabled" (identity-based, not tag-based), proving
    # the exclusion list wins over whatever category a spec.yaml claims.
    assert inv["by_category"]["disabled"] == 3


def test_build_manifest_evidence_table_column_count_tracks_active_angles():
    manifest = system_manifest_module.build_manifest(_sample_angles())
    active_count = manifest["active_angle_count"]
    fixed = len(system_manifest_module.FIXED_EVIDENCE_COLUMNS)
    assert manifest["evidence_table"]["fixed_columns"] == fixed
    assert manifest["evidence_table"]["active_indicator_columns"] == active_count
    assert manifest["evidence_table"]["total_columns"] == fixed + active_count


def test_build_manifest_flags_angle_missing_recording_time_format():
    angles = _sample_angles() + [_angle("only_daily_angle", "raw_data", time_formats=["1D"])]
    manifest = system_manifest_module.build_manifest(angles)
    assert "only_daily_angle" in manifest["angles_missing_recording_time_format"]


def test_build_manifest_column_count_changes_when_models_toggled_off(monkeypatch):
    angles = _sample_angles()
    manifest_on = system_manifest_module.build_manifest(angles)

    monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
    importlib.reload(model_policy_module)
    importlib.reload(system_manifest_module)
    manifest_off = system_manifest_module.build_manifest(angles)

    assert manifest_off["evidence_table"]["total_columns"] < manifest_on["evidence_table"]["total_columns"]
    assert manifest_off["policy_version"] != manifest_on["policy_version"]
