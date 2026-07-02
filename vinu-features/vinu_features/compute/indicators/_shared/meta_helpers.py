"""Helpers for parametric indicator modules."""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from vinu_features.compute.indicators._shared.spec import (
    column_matches_meta,
    default_params,
    meta_from_module,
    params_from_column_name,
    warmup_from_params,
)


def module_meta(mod: ModuleType) -> Any:
    return meta_from_module(mod)


def match_name(mod: ModuleType, name: str) -> bool:
    return column_matches_meta(module_meta(mod), name)


def params_for_name(mod: ModuleType, name: str) -> dict[str, int | float]:
    meta = module_meta(mod)
    parsed = params_from_column_name(meta, name)
    if parsed is not None:
        return parsed
    return default_params(meta)


def warmup_for_name(mod: ModuleType, name: str) -> int:
    meta = module_meta(mod)
    params = params_for_name(mod, name)
    return warmup_from_params(meta, params)


def this_module() -> ModuleType:
    return sys.modules[__name__.rsplit(".", 1)[0] + "." + sys._getframe(1).f_globals["__name__"].split(".")[-1]]
