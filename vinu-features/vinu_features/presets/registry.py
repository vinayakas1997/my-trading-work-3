"""Preset blueprints — re-export from bigger_recipe catalog."""

from __future__ import annotations

from dataclasses import dataclass

from vinu_features.compute.bigger_recipe import catalog


@dataclass(frozen=True)
class FeaturePreset:
    name: str
    features: tuple[str, ...]
    description: str = ""


def get_preset(name: str) -> FeaturePreset:
    key = name.strip().lower()
    if key not in catalog.list_recipe_names():
        known = ", ".join(sorted(catalog.list_recipe_names()))
        raise ValueError(f"Unknown preset '{name}'. Known: {known}")
    meta = catalog.get_recipe_meta(name)
    feats = catalog.resolve(name)
    return FeaturePreset(name=name.strip().lower(), features=tuple(feats), description=meta.get("description", ""))


def list_presets() -> list[FeaturePreset]:
    return [
        FeaturePreset(
            name=p["name"],
            features=tuple(p["features"]),
            description=p.get("description", ""),
        )
        for p in catalog.list_all_presets()
    ]


def resolve_features(*, preset: str | None, features: list[str]) -> list[str]:
    if preset and features:
        raise ValueError("Provide either preset or features, not both")
    if preset:
        return list(catalog.resolve(preset))
    if not features:
        raise ValueError("Either preset or features is required")
    return list(features)
