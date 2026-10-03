"""Phase 5 (items 5.1 / 5.2) of the-inconsistencies-v2: detective checks for look-ahead and
warmup drift (vinu_tools/compute/bias_checks.py), run over the real feature registry.

Also pins the two registry bugs those checks found while being built:
1. `Ref(...)`-based alpha expressions were silently all-None (354/360 alpha360 columns, 64/158
   alpha158, 25/101 alpha101): the evaluator's `ref` indexed a dict with a numpy array and the
   resulting TypeError was swallowed by a blanket `except`.
2. A single alpha feature requested by name (`ALPHA101_001`, `BETA10`) was dropped without error
   and its warmup was reported as 1 bar instead of 60: `expand_features` lowercases names but the
   alpha name sets are uppercase.
"""

from __future__ import annotations

import pytest

from vinu_tools.compute import bias_checks as bc
from vinu_tools.compute.registry import (
    _alpha_name_sets,
    apply_indicators,
    list_known_features,
    warmup_bars_for_features,
)

_RECIPE_NAMES = {
    "alpha101_benchmark", "alpha158", "alpha360", "basic_ta", "full_ta", "momentum",
    "mean_reversion_pack", "trend_pack", "volatility_pack", "volume_pack", "swing_basic",
}

# vinu-live's detector BASE_FEATURE_NAMES, copied here so vinu-tools never imports another service.
# vinu-live/tests/test_live_window_pinned.py pins the window these budgets were measured at (201 bars).
LIVE_BASE_FEATURES = [
    "adx_14", "rsi_14", "sma_5", "sma_10", "sma_20", "sma_50", "sma_100", "sma_200",
    "ema_5", "ema_10", "ema_20", "ema_50", "ema_100", "ema_200", "roc_5", "roc_10", "roc_20",
    "atr_14", "stoch_k_14", "stoch_d_14", "bb_upper_20", "bb_mid_20", "bb_lower_20", "macd",
    "macd_signal", "aroon_up", "aroon_down", "cci_20", "williams_r_14", "supertrend",
    "high_low_spread", "open_close_return", "momentum_10", "ichimoku_tenkan", "ichimoku_kijun",
    "ichimoku_senkou_a", "ichimoku_senkou_b", "parabolic_sar", "obv", "volume_ratio_20",
    "cmf_20", "mfi_14", "accumulation_distribution_line",
]
LIVE_WINDOW = 201


def _all_single_features() -> list[str]:
    a158, a360, a101 = _alpha_name_sets()
    return sorted((set(list_known_features()) - _RECIPE_NAMES) | a101 | a158 | a360)


# ------------------------------------------------------------------ the harness itself

def _leaky_compute(rows, names):
    """A feature that peeks one bar ahead -- the harness must flag it."""
    out = [dict(r) for r in rows]
    for i, r in enumerate(out):
        for n in names:
            r[n] = rows[min(i + 1, len(rows) - 1)]["close"] if n == "peek" else r["close"]
    return out


def test_harness_flags_a_one_bar_lookahead():
    rep = bc.lookahead_report(["peek"], rows=bc.synthetic_rows(120), compute=_leaky_compute)
    assert not rep.clean and rep.violations[0].feature == "peek"
    v = rep.violations[0]
    assert v.full_value != v.prefix_value and v.bar_index == v.cut - 1


def test_harness_passes_a_clean_feature_and_names_only_the_leaky_one():
    rep = bc.lookahead_report(["clean", "peek"], rows=bc.synthetic_rows(120), compute=_leaky_compute)
    assert [v.feature for v in rep.violations] == ["peek"]


def test_a_global_normalisation_leak_is_caught():
    def compute(rows, names):
        out = [dict(r) for r in rows]
        mean = sum(r["close"] for r in rows) / len(rows)  # whole-series statistic -> value depends on the future
        for r in out:
            r["g"] = r["close"] / mean
        return out

    assert [v.feature for v in bc.lookahead_report(["g"], rows=bc.synthetic_rows(120), compute=compute).violations] == ["g"]


def test_an_all_none_feature_is_unverifiable_not_clean():
    """The check that found the dead alpha family: comparing None with None proves nothing."""
    rep = bc.lookahead_report(["dead"], rows=bc.synthetic_rows(120), compute=lambda rows, names: [dict(r, dead=None) for r in rows])
    assert rep.unverifiable == ["dead"] and rep.clean  # no violation, but explicitly NOT verified


def test_a_feature_changing_from_none_to_a_value_is_a_violation():
    def compute(rows, names):
        n = len(rows)
        return [dict(r, f=(1.0 if i < n - 1 else None)) for i, r in enumerate(rows)]

    assert not bc.lookahead_report(["f"], rows=bc.synthetic_rows(120), compute=compute).clean


def test_warmup_drift_is_zero_for_a_windowed_feature_and_positive_for_a_recursive_one():
    rows = bc.synthetic_rows(800)

    def compute(rs, names):
        out = [dict(r) for r in rs]
        ema, run = [], None
        for r in rs:
            run = r["close"] if run is None else 0.9 * run + 0.1 * r["close"]
            ema.append(run)
        for i, r in enumerate(out):
            r["window"] = sum(x["close"] for x in rs[max(0, i - 4): i + 1]) / len(rs[max(0, i - 4): i + 1])
            r["recursive"] = ema[i]
        return out

    d = bc.warmup_drift(["window", "recursive"], window=10, rows=rows, compute=compute)
    assert d["window"] == pytest.approx(0.0, abs=1e-12) and d["recursive"] > 1e-4


def test_warmup_drift_rejects_a_bad_window():
    with pytest.raises(ValueError):
        bc.warmup_drift(["sma_20"], window=1)
    with pytest.raises(ValueError):
        bc.warmup_drift(["sma_20"], window=10_000, rows=bc.synthetic_rows(100))


# ------------------------------------------------------------------ the real registry

def test_no_registered_feature_looks_ahead():
    rep = bc.lookahead_report(_all_single_features())
    assert rep.clean, [(v.feature, v.cut, v.bar_index, v.full_value, v.prefix_value) for v in rep.violations[:10]]


def test_no_registered_feature_is_silently_unverifiable():
    """Every feature must actually produce a value on ordinary single-symbol OHLCV. A non-empty list
    here means a feature is dead (the alpha family was, until the Ref fix) -- fix it, do not extend this."""
    rep = bc.lookahead_report(_all_single_features())
    assert rep.unverifiable == [], f"{len(rep.unverifiable)} dead features, e.g. {rep.unverifiable[:8]}"


# Relative drift allowed between the live window (201 bars) and full history, per feature. Measured
# worst cases over several random paths are in the comments; a regression (or a live-window change)
# has to move these numbers consciously. Cumulative-from-start features are checked separately.
_DEFAULT_BUDGET = 5e-4          # worst measured elsewhere: ema_50 ~3e-5, macd_signal ~1e-5, adx ~5e-6
_BUDGETS = {
    "ema_100": 1e-2,            # measured up to ~0.4%: an EMA-100 has not converged in 201 bars
    "ema_200": 1e-1,            # measured up to ~4.5%: far from converged; trend filters on it differ live vs backtest
    "supertrend": 2.5e-1,       # measured up to ~11%: path dependent (flip state)
}


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_live_window_drift_stays_within_budget(seed):
    names = [n for n in LIVE_BASE_FEATURES if n not in bc.CUMULATIVE_FEATURES]
    drift = bc.warmup_drift(names, window=LIVE_WINDOW, rows=bc.synthetic_rows(1200, seed=seed))
    over = {n: d for n, d in drift.items() if d is not None and d > _BUDGETS.get(n, _DEFAULT_BUDGET)}
    assert not over, f"live-vs-backtest drift above budget at a {LIVE_WINDOW}-bar window (seed {seed}): {over}"
    assert all(d is not None for d in drift.values()), [n for n, d in drift.items() if d is None]


# Same check at the enlarged window the A8 fix recommends (live_decision_feature_window_bars=600).
# Measured worst over 5 paths: ema_200 5.5e-4, ema_100 9e-7, everything else < 1e-9. supertrend does NOT
# converge with a longer window (flip-state, ~14% at any size): it is path dependent, not warmup limited.
_BUDGETS_600 = {"ema_200": 2e-3, "supertrend": 2.5e-1}


@pytest.mark.parametrize("seed", [11, 12, 13])
def test_enlarged_live_window_converges_slow_emas(seed):
    names = [n for n in LIVE_BASE_FEATURES if n not in bc.CUMULATIVE_FEATURES]
    drift = bc.warmup_drift(names, window=600, rows=bc.synthetic_rows(1500, seed=seed))
    over = {n: d for n, d in drift.items() if d is not None and d > _BUDGETS_600.get(n, 1e-5)}
    assert not over, f"drift above budget at a 600-bar window (seed {seed}): {over}"
    short = bc.warmup_drift(["ema_200"], window=LIVE_WINDOW, rows=bc.synthetic_rows(1500, seed=seed))["ema_200"]
    assert drift["ema_200"] < short  # the larger window is strictly closer to backtest


def test_cumulative_features_are_documented_as_level_dependent():
    """OBV / accumulation-distribution / VWAP accumulate from the first bar, so a short live window can
    never reproduce a long-history LEVEL. Pinned so a future fix flips this test on purpose, and so nobody
    compares their absolute values across windows without knowing."""
    d = bc.warmup_drift(sorted(bc.CUMULATIVE_FEATURES), window=LIVE_WINDOW, rows=bc.synthetic_rows(1200))
    assert min(v for v in d.values() if v is not None) > 0.05


# ------------------------------------------------------------------ bug 1: Ref(...) alpha expressions

def test_ref_based_alpha_columns_now_have_values_and_the_right_lag():
    rows = bc.synthetic_rows(300)
    out = apply_indicators(rows, ["CLOSE5"])
    t = 200
    assert out[t]["CLOSE5"] == pytest.approx(rows[t - 5]["close"] / rows[t]["close"])
    assert out[4]["CLOSE5"] is None and out[5]["CLOSE5"] is not None  # NaN before the lag exists


@pytest.mark.parametrize("recipe", ["alpha101_benchmark", "alpha158", "alpha360"])
def test_no_alpha_recipe_column_is_all_none(recipe):
    from vinu_tools.compute.registry import recipe_catalog

    cols = recipe_catalog.compute_recipe(bc.synthetic_rows(400), recipe)
    dead = [k for k, v in cols.items() if all(x is None for x in v)]
    assert not dead, f"{recipe}: {len(dead)} of {len(cols)} columns never produce a value, e.g. {dead[:6]}"


def test_evaluator_still_returns_none_for_a_genuinely_unevaluable_expression():
    """The blanket-except contract is unchanged (a bad expression is a None column, not a crash)."""
    from vinu_tools.compute.factors.recipes._alpha_expr.evaluator import evaluate, rows_to_arrays

    arrays = rows_to_arrays(bc.synthetic_rows(50))
    assert evaluate("NoSuchOperator($close, 3)", arrays) == [None] * 50


# ------------------------------------------------------------------ bug 2: individually-named alpha features

@pytest.mark.parametrize("name", ["ALPHA101_001", "alpha101_001", "BETA10", "beta10", "CLOSE1", "close1"])
def test_a_single_alpha_feature_requested_by_name_is_computed(name):
    out = apply_indicators(bc.synthetic_rows(300), [name])
    keys = [k for k in out[-1] if k.upper() == name.upper()]
    assert keys, f"{name!r} produced no column"
    assert out[-1][keys[0]] is not None


def test_a_single_alpha_matches_the_same_column_from_the_whole_recipe():
    rows = bc.synthetic_rows(300)
    whole = apply_indicators(rows, ["alpha101_benchmark"])
    single = apply_indicators(rows, ["ALPHA101_001"])
    assert single[-1]["ALPHA101_001"] == whole[-1]["ALPHA101_001"]


def test_single_alpha_warmup_is_the_recipes_not_one_bar():
    assert warmup_bars_for_features(["ALPHA101_001"]) == warmup_bars_for_features(["alpha101_benchmark"]) == 60
    assert warmup_bars_for_features(["BETA10"]) == 60


def test_non_alpha_features_are_unchanged_by_the_name_fix():
    assert warmup_bars_for_features(["sma_50"]) == 51
    out = apply_indicators(bc.synthetic_rows(120), ["sma_20", "rsi_14"])
    assert out[-1]["sma_20"] is not None and out[-1]["rsi_14"] is not None
    assert "ALPHA101_001" not in out[-1]
