"""Alpha360 field definitions (qlib Alpha360DL port)."""

from __future__ import annotations


def get_feature_config() -> tuple[list[str], list[str]]:
    fields: list[str] = []
    names: list[str] = []
    for i in range(59, 0, -1):
        fields.append(f"Ref($close, {i})/$close")
        names.append(f"CLOSE{i}")
    fields.append("$close/$close")
    names.append("CLOSE0")
    for i in range(59, 0, -1):
        fields.append(f"Ref($open, {i})/$close")
        names.append(f"OPEN{i}")
    fields.append("$open/$close")
    names.append("OPEN0")
    for i in range(59, 0, -1):
        fields.append(f"Ref($high, {i})/$close")
        names.append(f"HIGH{i}")
    fields.append("$high/$close")
    names.append("HIGH0")
    for i in range(59, 0, -1):
        fields.append(f"Ref($low, {i})/$close")
        names.append(f"LOW{i}")
    fields.append("$low/$close")
    names.append("LOW0")
    for i in range(59, 0, -1):
        fields.append(f"Ref($vwap, {i})/$close")
        names.append(f"VWAP{i}")
    fields.append("$vwap/$close")
    names.append("VWAP0")
    for i in range(59, 0, -1):
        fields.append(f"Ref($volume, {i})/($volume+1e-12)")
        names.append(f"VOLUME{i}")
    fields.append("$volume/($volume+1e-12)")
    names.append("VOLUME0")
    return fields, names


NAME = "alpha360"
DESCRIPTION = "qlib Alpha360 normalized OHLCV"
WARMUP_BARS = 60


def resolve() -> tuple[str, ...]:
    _, names = get_feature_config()
    return tuple(names)


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    from vinu_features.compute.bigger_recipe._alpha_expr.compute_alpha import compute_alpha

    return compute_alpha(rows, get_feature_config)
