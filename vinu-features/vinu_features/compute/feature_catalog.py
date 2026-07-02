"""Discover indicator metadata and presets."""

from __future__ import annotations

import importlib
from typing import Any

from vinu_features.compute.indicators._module_names import INDICATOR_MODULE_NAMES
from vinu_features.compute.indicators._shared.spec import IndicatorMeta, meta_from_module
from vinu_features.presets import registry as preset_registry

_MODULES: list[Any] | None = None
_META_BY_KIND: dict[str, IndicatorMeta] | None = None


def _load_modules() -> list[Any]:
    global _MODULES
    if _MODULES is None:
        _MODULES = [
            importlib.import_module(f"vinu_features.compute.indicators.{name}.{name}")
            for name in INDICATOR_MODULE_NAMES
        ]
    return _MODULES


def _load_meta() -> dict[str, IndicatorMeta]:
    global _META_BY_KIND
    if _META_BY_KIND is None:
        _META_BY_KIND = {}
        for mod in _load_modules():
            if hasattr(mod, "KIND"):
                meta = meta_from_module(mod)
                _META_BY_KIND[meta.kind] = meta
    return _META_BY_KIND


def list_indicators() -> list[IndicatorMeta]:
    return [_load_meta()[k] for k in sorted(_load_meta())]


def get_indicator(kind: str) -> IndicatorMeta:
    key = kind.strip().lower()
    meta = _load_meta().get(key)
    if meta is None:
        raise ValueError(f"Unknown indicator kind: {kind}")
    return meta


def get_indicator_module(kind: str) -> Any:
    key = kind.strip().lower()
    for mod in _load_modules():
        if getattr(mod, "KIND", None) == key:
            return mod
    raise ValueError(f"Unknown indicator kind: {kind}")


def list_indicator_kinds() -> list[str]:
    return sorted(_load_meta())


def list_presets() -> list[dict]:
    return [
        {
            "name": p.name,
            "description": p.description,
            "features": list(p.features),
            "feature_count": len(p.features),
        }
        for p in preset_registry.list_presets()
    ]


def format_help(kind: str | None = None) -> str:
    if kind:
        meta = get_indicator(kind)
        lines = [
            f"{meta.kind} — {meta.description}",
            "",
            "Params:",
        ]
        if meta.params:
            for name, pdef in meta.params.items():
                bounds = ""
                if pdef.min is not None or pdef.max is not None:
                    bounds = f" (min={pdef.min}, max={pdef.max})"
                lines.append(f"  {name}: {pdef.type}, default={pdef.default}{bounds}")
        else:
            lines.append("  (none)")
        lines.extend(["", "Output columns:"])
        for col in meta.output_columns:
            lines.append(f"  {col}")
        lines.extend(["", "Examples (CLI):"])
        for ex in meta.examples:
            if ":" in ex or ex == meta.kind:
                lines.append(f"  --feature {ex}")
            else:
                lines.append(f"  --features {ex}")
        lines.extend(["", "Examples (HTTP):"])
        for ex in meta.examples:
            if ex == meta.kind:
                lines.append(f'  {{"kind": "{meta.kind}", "params": {{}}}}')
            elif ":" in ex and ex.startswith(meta.kind):
                _, rest = ex.split(":", 1)
                parts = rest.split(",")
                params = {}
                for part in parts:
                    k, v = part.split("=", 1)
                    params[k.strip()] = int(v) if v.isdigit() else float(v)
                lines.append(f'  {{"kind": "{meta.kind}", "params": {params}}}')
            else:
                lines.append(f'  "{ex}"')
        return "\n".join(lines)

    lines = ["Indicators:", ""]
    for meta in list_indicators():
        param_summary = ", ".join(f"{k}={p.default}" for k, p in meta.params.items()) or "none"
        lines.append(f"  {meta.kind:<22} {meta.description}  [{param_summary}]")
    lines.extend(["", "Presets:", ""])
    for p in preset_registry.list_presets():
        lines.append(f"  {p.name:<22} {p.description}  ({len(p.features)} features)")
    lines.extend(["", "Run: vinu-features features help <kind>"])
    return "\n".join(lines)


def indicator_meta_to_dict(meta: IndicatorMeta) -> dict:
    return {
        "kind": meta.kind,
        "description": meta.description,
        "params": {
            k: {
                "type": v.type,
                "default": v.default,
                "min": v.min,
                "max": v.max,
            }
            for k, v in meta.params.items()
        },
        "output_columns": list(meta.output_columns),
        "examples": list(meta.examples),
        "legacy_aliases": meta.legacy_aliases,
    }
