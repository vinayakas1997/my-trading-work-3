from __future__ import annotations

from vinu_tools.compute.registry import (
    format_indicator_help,
    get_indicator,
    get_indicator_module,
    list_indicator_kinds,
    list_indicators,
    list_presets,
)

format_help = format_indicator_help

from vinu_tools.compute.indicators._shared.spec import IndicatorMeta


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


__all__ = [
    "format_indicator_help", "format_help", "get_indicator", "get_indicator_module",
    "indicator_meta_to_dict", "list_indicators", "list_indicator_kinds", "list_presets",
    "IndicatorMeta",
]
