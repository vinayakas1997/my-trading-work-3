"""Indicator metadata types and column resolution helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ParamDef:
    type: str
    default: int | float
    min: int | float | None = None
    max: int | float | None = None


@dataclass(frozen=True)
class IndicatorMeta:
    kind: str
    description: str
    params: dict[str, ParamDef]
    output_columns: tuple[str, ...]
    examples: tuple[str, ...]
    legacy_aliases: dict[str, dict[str, int | float]] = field(default_factory=dict)


def param_def_from_dict(raw: dict[str, Any]) -> ParamDef:
    return ParamDef(
        type=str(raw["type"]),
        default=raw["default"],
        min=raw.get("min"),
        max=raw.get("max"),
    )


def meta_from_module(mod: Any) -> IndicatorMeta:
    params_raw = getattr(mod, "PARAMS", {})
    params = {k: param_def_from_dict(v) for k, v in params_raw.items()}
    return IndicatorMeta(
        kind=str(getattr(mod, "KIND", "")),
        description=str(getattr(mod, "DESCRIPTION", "")),
        params=params,
        output_columns=tuple(getattr(mod, "OUTPUT_COLUMNS", ())),
        examples=tuple(getattr(mod, "EXAMPLES", ())),
        legacy_aliases=dict(getattr(mod, "LEGACY_ALIASES", {})),
    )


def default_params(meta: IndicatorMeta) -> dict[str, int | float]:
    return {name: pdef.default for name, pdef in meta.params.items()}


def format_columns(meta: IndicatorMeta, params: dict[str, int | float]) -> tuple[str, ...]:
    if not meta.output_columns:
        return (meta.kind,)
    merged = {**default_params(meta), **params}
    out: list[str] = []
    for template in meta.output_columns:
        out.append(template.format(**merged))
    return tuple(out)


def warmup_from_params(meta: IndicatorMeta, params: dict[str, int | float]) -> int:
    merged = {**default_params(meta), **params}
    period = int(merged.get("period", 1))
    smooth = int(merged.get("smooth", 0))
    if meta.kind == "adx":
        return period * 2
    if meta.kind in ("macd", "macd_signal"):
        return 34
    if meta.kind == "aroon":
        return period + 1
    if meta.kind == "stochastic":
        return period + smooth
    if meta.kind == "supertrend":
        return period + 1
    if meta.kind in ("rsi", "atr", "williams_r"):
        return period + 1
    if meta.kind in ("sma", "ema"):
        return period
    if meta.kind in ("cci", "cmf", "bollinger", "volatility", "volume_ratio"):
        return period + 1
    if meta.kind in ("roc", "momentum"):
        return period + 1
    if meta.kind == "volatility_20d":
        return period + 1
    return period + 1


def validate_params(meta: IndicatorMeta, params: dict[str, Any]) -> dict[str, int | float]:
    validated: dict[str, int | float] = {}
    unknown = set(params) - set(meta.params)
    if unknown:
        raise ValueError(
            f"{meta.kind}: unknown param(s) {sorted(unknown)}. "
            f"Valid: {sorted(meta.params)}"
        )
    for name, pdef in meta.params.items():
        if name not in params:
            continue
        raw = params[name]
        if pdef.type == "int":
            try:
                val = int(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{meta.kind}.{name} must be int >= {pdef.min}, got {raw!r}"
                ) from exc
        else:
            try:
                val = float(raw)
            except (TypeError, ValueError) as exc:
                raise ValueError(
                    f"{meta.kind}.{name} must be float, got {raw!r}"
                ) from exc
        if pdef.min is not None and val < pdef.min:
            raise ValueError(f"{meta.kind}.{name} must be >= {pdef.min}, got {val}")
        if pdef.max is not None and val > pdef.max:
            raise ValueError(f"{meta.kind}.{name} must be <= {pdef.max}, got {val}")
        validated[name] = val
    return validated


def params_from_column_name(meta: IndicatorMeta, column: str) -> dict[str, int | float] | None:
    if column in meta.legacy_aliases:
        return dict(meta.legacy_aliases[column])

    merged_defaults = default_params(meta)
    if not meta.params:
        if column in meta.legacy_aliases:
            return dict(meta.legacy_aliases[column])
        if column in meta.output_columns or column == meta.kind:
            return {}
        return None

    # kind_suffix patterns e.g. rsi_20, sma_100, atr_14
    if len(meta.params) == 1 and "period" in meta.params:
        m = re.match(rf"^{re.escape(meta.kind)}_(\d+)$", column)
        if m:
            return {"period": int(m.group(1))}

    if meta.kind == "volatility":
        m = re.match(r"^volatility_(\d+)d$", column)
        if m:
            return {"period": int(m.group(1))}

    if meta.kind == "volume_ratio":
        m = re.match(r"^volume_ratio_(\d+)$", column)
        if m:
            return {"period": int(m.group(1))}

    if meta.kind == "momentum":
        m = re.match(r"^momentum_(\d+)$", column)
        if m:
            return {"period": int(m.group(1))}

    if meta.kind == "williams_r":
        m = re.match(r"^williams_r_(\d+)$", column)
        if m:
            return {"period": int(m.group(1))}

    # single template output e.g. volatility_20d, volume_ratio_20
    for template in meta.output_columns:
        if "{" not in template:
            if column == template:
                return {}
            continue
        pattern = "^" + re.escape(template).replace(r"\{period\}", r"(?P<period>\d+)").replace(
            r"\{smooth\}", r"(?P<smooth>\d+)"
        ).replace(r"\{std\}", r"(?P<std>[\d.]+)") + "$"
        m = re.match(pattern, column)
        if m:
            out: dict[str, int | float] = dict(merged_defaults)
            for key, val in m.groupdict().items():
                if val is not None:
                    out[key] = int(val) if key != "std" else float(val)
            return out

    # multi-column legacy names bb_upper, stoch_k without suffix
    if column in meta.legacy_aliases:
        return dict(meta.legacy_aliases[column])

    for alias, param_overrides in meta.legacy_aliases.items():
        if column == alias:
            return dict(param_overrides)

    # bollinger bb_upper_20 style
    if meta.kind == "bollinger":
        m = re.match(r"^bb_(upper|mid|lower)_(\d+)$", column)
        if m:
            return {"period": int(m.group(2)), "std": merged_defaults.get("std", 2.0)}
    if meta.kind == "stochastic":
        m = re.match(r"^stoch_[kd]_(\d+)$", column)
        if m:
            return {"period": int(m.group(1)), "smooth": merged_defaults.get("smooth", 3)}

    return None


def column_matches_meta(meta: IndicatorMeta, column: str) -> bool:
    if params_from_column_name(meta, column) is not None:
        return True
    if not meta.params and column in meta.output_columns:
        return True
    return column in meta.legacy_aliases
