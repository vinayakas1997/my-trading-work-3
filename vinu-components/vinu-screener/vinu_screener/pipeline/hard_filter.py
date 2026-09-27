"""Stage B (B11): `HardFilterConfig` -- the declarative, fielded shape for
a screener rule's numeric filter bands, ported from daily_stock_analysis's
`src/services/screening/models.py` (~35 knobs there; this is a
representative subset covering the same categories: price/volume, valuation,
technical status, and a minimum composite-signal floor -- extend this
dataclass with more fields as real rules need them, same "add a field, don't
redesign" convention `RuntimeSettings.register()` uses elsewhere in Vina).

Distinct from B7's `CoarseFilter`: `CoarseFilter` is the *cheap, pre-fetch*
universe-wide gate (price/volume/dollar_volume only, run before anything is
fetched). `HardFilterConfig` is the *richer, post-fetch* filter run once a
candidate's full feature set (fundamentals + technicals, however sourced) is
available -- DSA's pipeline runs both stages for the same reason: don't pay
for a full feature computation on a symbol the cheap filter would have
rejected anyway.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class HardFilterConfig:
    """All bounds are inclusive; `None` means "no bound on this field" (an
    all-`None` config passes everything). Field names match the keys a
    candidate's `fields` dict is expected to carry for the bounds actually
    set -- a rule only needs to supply the feature values its own filter
    bands reference.

    item #18 finding #2: `min_volume`/`min_dollar_volume` default to
    `None` -- nothing protects Layer 5's position sizing from an illiquid
    name slipping through a ranker that doesn't set one. Deliberately
    left as a documented recommendation, not a changed class default:
    flipping the default here would silently change the live behavior of
    any already-configured ranker that currently has no floor set (a
    reload picks up a dataclass default change immediately, per
    `RankerConfig.from_dict`'s `HardFilterConfig(**raw.get("hard_filter",
    {}))`), which is a real, hard-to-reverse behavior change this finding's
    own "low severity, worth a documented default" framing doesn't ask
    for. `rankers/seed.py`'s `CORE_STARTER_HARD_FILTER` already answers
    "what's a reasonable floor" for the one ranker that ships seeded by
    default (`min_price=5.0, min_dollar_volume=1_000_000.0`) -- reuse
    that same pair of numbers for any *new* ranker you configure, unless
    you have a specific reason not to.
    """

    min_price: float | None = None
    max_price: float | None = None
    min_volume: float | None = None
    min_dollar_volume: float | None = None
    min_market_cap: float | None = None
    max_market_cap: float | None = None
    pe_min: float | None = None
    pe_max: float | None = None
    pb_min: float | None = None
    pb_max: float | None = None
    min_volume_ratio: float | None = None
    max_turnover: float | None = None
    min_turnover: float | None = None
    signal_score_min: float | None = None
    # item #18 finding #1: neither this config nor CoarseFilter (scan/
    # universe.py) had any minimum-history bound at all -- a thinly-traded
    # or recently-listed symbol with as few as 30 bars could land in a
    # ranker's top-N even though Track 1's signal_evidence needs
    # min_observations=70 before it does anything useful with that ticker.
    # Checked in RankerRunner.run(), before factor computation -- not one
    # of _BOUND_FIELDS below, since it reads the OHLCV frame's own bar
    # count, not a `fields` value computed from it.
    min_history_bars: int | None = None


_BOUND_FIELDS: tuple[tuple[str, str, str], ...] = (
    # (config attr, candidate field key, comparison: "min" or "max")
    ("min_price", "price", "min"),
    ("max_price", "price", "max"),
    ("min_volume", "volume", "min"),
    ("min_dollar_volume", "dollar_volume", "min"),
    ("min_market_cap", "market_cap", "min"),
    ("max_market_cap", "market_cap", "max"),
    ("pe_min", "pe", "min"),
    ("pe_max", "pe", "max"),
    ("pb_min", "pb", "min"),
    ("pb_max", "pb", "max"),
    ("min_volume_ratio", "volume_ratio", "min"),
    ("max_turnover", "turnover", "max"),
    ("min_turnover", "turnover", "min"),
    ("signal_score_min", "signal_score", "min"),
)


def _clean(value: object) -> float | None:
    try:
        v = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def hard_filter_reasons(fields: dict[str, float], cfg: HardFilterConfig) -> list[str]:
    """The bound(s) `fields` fails against `cfg`, empty if it passes all of
    them. A field that's missing or non-finite fails every bound that reads
    it -- same fail-closed posture as B2's `all_finite` and B7's
    `passes_coarse`: an unpriceable/undated symbol shouldn't quietly survive
    a filter it can't actually be checked against. Returning reasons (not
    just a bool) is what B19's dry-run diagnostics (Phase B-4) will read."""
    reasons: list[str] = []
    for attr, key, kind in _BOUND_FIELDS:
        bound = getattr(cfg, attr)
        if bound is None:
            continue
        v = _clean(fields.get(key))
        if v is None:
            reasons.append(f"{key} missing or non-finite (needed for {attr})")
            continue
        if kind == "min" and v < bound:
            reasons.append(f"{key}={v} < {attr}={bound}")
        elif kind == "max" and v > bound:
            reasons.append(f"{key}={v} > {attr}={bound}")
    return reasons


def passes_hard_filter(fields: dict[str, float], cfg: HardFilterConfig) -> bool:
    return not hard_filter_reasons(fields, cfg)
