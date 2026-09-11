"""Stage B (B12): risk-overlay-as-penalty-not-filter, ported from
daily_stock_analysis's `apply_risk_overlay` (`src/services/screening/
risk.py:50-83,141-199`). A hard filter (B11) is binary -- fails a bound,
gone. A risk overlay instead *scores* a set of independent risk signals as
bounded, additive penalty points against a candidate that already passed
the hard filter, so a borderline-risky-but-otherwise-strong candidate stays
visible (lower-ranked, flagged) rather than disappearing outright -- with an
optional hard veto for risk severe enough that DSA's own tracker language
calls it "no, not even ranked last."

Each `RiskCheck` is independent and declarative (name, predicate over a
candidate's `fields`, penalty points, optional veto-on-trigger) so adding a
new risk signal is "register one more `RiskCheck`", not touching this
module's control flow -- same "add a rule, don't redesign the runner"
convention as `FeatureLibrary.register()` and `RuntimeSettings.register()`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable


@dataclass(frozen=True)
class RiskCheck:
    name: str
    predicate: Callable[[dict[str, float]], bool]  # True == this risk is present
    penalty: float
    veto: bool = False


def _get(fields: dict[str, float], key: str) -> float | None:
    try:
        v = float(fields.get(key))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _missing(key: str) -> Callable[[dict[str, float]], bool]:
    return lambda f: _get(f, key) is None


def _above(key: str, threshold: float) -> Callable[[dict[str, float]], bool]:
    return lambda f: (v := _get(f, key)) is not None and v > threshold


def _below(key: str, threshold: float) -> Callable[[dict[str, float]], bool]:
    return lambda f: (v := _get(f, key)) is not None and v < threshold


def _flag_true(key: str) -> Callable[[dict[str, float]], bool]:
    return lambda f: bool(f.get(key))


# DSA's own named risk categories (risk.py:50-83), reimplemented as
# threshold checks over a candidate's `fields` dict. `chase_pct`/
# `breakdown_pct` are momentum-since-signal fields a rule computes upstream;
# `volume_ratio`/`turnover`/`pe`/`pb`/`rsi`/`macd_bearish`/`llm_confidence`
# match DSA's own field names so a ported rule config needs no translation.
# Data-quality risk (stale cache / fetch failure / fallback path) is
# included for the same reason DSA includes it: a candidate built from
# degraded data is itself a risk, independent of what its numbers say.
DEFAULT_RISK_CHECKS: tuple[RiskCheck, ...] = (
    RiskCheck("chase_momentum", _above("chase_pct", 0.15), penalty=8.0),
    RiskCheck("breakdown_momentum", _below("breakdown_pct", -0.10), penalty=10.0),
    RiskCheck("abnormal_volume_ratio", _above("volume_ratio", 5.0), penalty=6.0),
    RiskCheck("high_turnover", _above("turnover", 0.20), penalty=5.0),
    RiskCheck("invalid_pe", lambda f: (v := _get(f, "pe")) is not None and v <= 0, penalty=4.0),
    RiskCheck("high_pb", _above("pb", 10.0), penalty=4.0),
    RiskCheck("macd_bearish", _flag_true("macd_bearish"), penalty=5.0),
    RiskCheck("rsi_overbought", _above("rsi", 80.0), penalty=5.0),
    RiskCheck("low_llm_confidence", _below("llm_confidence", 0.4), penalty=6.0),
    RiskCheck("llm_declared_risk", _flag_true("llm_risk_flag"), penalty=8.0),
    RiskCheck("deep_analysis_risk_flag", _flag_true("deep_analysis_risk_flag"), penalty=8.0),
    RiskCheck("stale_data", _flag_true("data_stale"), penalty=10.0),
    RiskCheck("fetch_degraded", _flag_true("data_fetch_degraded"), penalty=10.0),
)


@dataclass(frozen=True)
class RiskOverlayConfig:
    checks: tuple[RiskCheck, ...] = DEFAULT_RISK_CHECKS
    max_penalty: float = 30.0          # bounded/capped, per the tracker item's own wording
    veto_penalty_threshold: float | None = None   # e.g. 25.0: total penalty this high also vetoes
    veto_high_risk: bool = False       # DSA's own flag name -- any single-check veto=True also vetoes


@dataclass
class RiskOverlayResult:
    penalty: float
    flags: list[str] = field(default_factory=list)
    vetoed: bool = False
    veto_reason: str = ""


def apply_risk_overlay(fields: dict[str, float], cfg: RiskOverlayConfig = RiskOverlayConfig()) -> RiskOverlayResult:
    flags: list[str] = []
    raw_penalty = 0.0
    veto = False
    veto_reason = ""
    for check in cfg.checks:
        try:
            triggered = check.predicate(fields)
        except Exception:  # noqa: BLE001 -- one malformed field must not abort scoring
            continue
        if not triggered:
            continue
        flags.append(check.name)
        raw_penalty += check.penalty
        if check.veto and cfg.veto_high_risk:
            veto = True
            veto_reason = veto_reason or f"hard-veto risk: {check.name}"

    penalty = min(raw_penalty, cfg.max_penalty)
    if cfg.veto_penalty_threshold is not None and penalty >= cfg.veto_penalty_threshold:
        veto = True
        veto_reason = veto_reason or f"penalty {penalty} >= veto threshold {cfg.veto_penalty_threshold}"

    return RiskOverlayResult(penalty=penalty, flags=flags, vetoed=veto, veto_reason=veto_reason)
