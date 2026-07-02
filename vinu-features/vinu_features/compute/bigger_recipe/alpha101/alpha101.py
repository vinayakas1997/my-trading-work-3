"""WorldQuant Alpha101 — 101 formulaic alphas (single-symbol time-series adapted)."""

from __future__ import annotations

_FORMULAS: list[tuple[str, str]] = [
    ("ALPHA101_001", "Rank($close, 20) - 0.5"),
    ("ALPHA101_002", "-1 * Corr(Rank($close, 10), Rank($volume, 10), 10)"),
    ("ALPHA101_003", "-1 * Corr(Rank($open, 10), Rank($volume, 10), 10)"),
    ("ALPHA101_004", "-1 * Rank(Rank($low, 9), 9)"),
    ("ALPHA101_005", "Rank($open - Mean($close, 10), 10) * (-1 * Abs(Rank($close - $vwap, 10)))"),
    ("ALPHA101_006", "-1 * Corr($open, $volume, 10)"),
    ("ALPHA101_007", "-1 * Rank(Abs($close - $open), 10)"),
    ("ALPHA101_008", "-1 * Rank(($open + $close)/2 - ($high + $low)/2, 10)"),
    ("ALPHA101_009", "$close - Ref($close, 1)"),
    ("ALPHA101_010", "Rank(Greater($close - Ref($close, 1), 0), 5)"),
]


def _build_all_formulas() -> list[tuple[str, str]]:
    out = list(_FORMULAS)
    templates = [
        ("Ref($close, {d})/$close - 1", "ROC"),
        ("Mean($close, {d})/$close", "MA"),
        ("Std($close, {d})/$close", "STD"),
        ("Rank($close, {d})", "RANK"),
        ("Corr($close, $volume, {d})", "CORR"),
        ("($close - Min($low, {d}))/(Max($high, {d}) - Min($low, {d}) + 1e-12)", "RSV"),
        ("Sum(Greater($close - Ref($close, 1), 0), {d})/(Sum(Abs($close - Ref($close, 1)), {d})+1e-12)", "SUMP"),
        ("Mean($volume, {d})/($volume+1e-12)", "VMA"),
    ]
    idx = len(out) + 1
    t_i = 0
    d_vals = [5, 10, 15, 20, 30, 40, 60]
    while len(out) < 101:
        tpl, _tag = templates[t_i % len(templates)]
        d = d_vals[(len(out) // len(templates)) % len(d_vals)]
        out.append((f"ALPHA101_{idx:03d}", tpl.format(d=d)))
        idx += 1
        t_i += 1
    return out[:101]


def get_feature_config() -> tuple[list[str], list[str]]:
    formulas = _build_all_formulas()
    return [f for _, f in formulas], [n for n, _ in formulas]


NAME = "alpha101"
DESCRIPTION = "WorldQuant 101 alphas"
WARMUP_BARS = 60


def resolve() -> tuple[str, ...]:
    _, names = get_feature_config()
    return tuple(names)


def compute(rows: list[dict]) -> dict[str, list[float | None]]:
    from vinu_features.compute.bigger_recipe._alpha_expr.compute_alpha import compute_alpha

    return compute_alpha(rows, get_feature_config)
