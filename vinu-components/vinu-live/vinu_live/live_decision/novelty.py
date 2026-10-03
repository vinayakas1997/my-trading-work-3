"""Input-novelty check (v2 B1): how unlike its own recent history is the live feature vector?

Dissimilarity-Index style (the simplest member of the FreqAI outlier family): standardise every feature by the
reference history's mean / std, take the mean distance from the live vector to its k nearest reference points, and
divide by the reference's own typical nearest-neighbour distance (each reference point against the others). A ratio
near 1 means "looks like what we have seen"; well above 1 means "unlike anything in the reference".

The reference is the ticker's own previously recorded live snapshots, so no new store is needed. Pure functions:
no I/O, never raises on bad data -- an unusable reference reports `insufficient_reference` (unknown, NOT novel).
"""

from __future__ import annotations

import math
from typing import Any

DEFAULT_K = 5
DEFAULT_MIN_REFERENCE = 30
DEFAULT_RATIO_THRESHOLD = 2.0
_MIN_COVERAGE = 0.9   # a feature must be present in at least this share of reference rows to be used


def _num(v: Any) -> float | None:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    f = float(v)
    return f if math.isfinite(f) else None


def _mean_knn(dists: list[float], k: int) -> float:
    return sum(sorted(dists)[:k]) / min(k, len(dists))


def novelty_ratio(
    current: dict[str, Any], reference: list[dict[str, Any]], *, k: int = DEFAULT_K,
    min_reference: int = DEFAULT_MIN_REFERENCE, ratio_threshold: float = DEFAULT_RATIO_THRESHOLD,
) -> dict[str, Any]:
    """`{status, ratio, novelty_high, n_reference, n_features}`; status is ok | insufficient_reference."""
    def unknown(reason: str, n_ref: int = 0, n_feat: int = 0) -> dict[str, Any]:
        return {"status": "insufficient_reference", "ratio": None, "novelty_high": False,
                "n_reference": n_ref, "n_features": n_feat, "reason": reason}

    if len(reference) < max(min_reference, k + 2):
        return unknown(f"{len(reference)} reference snapshots (< {max(min_reference, k + 2)})", len(reference))

    names: list[str] = []
    for name, value in current.items():
        if _num(value) is None:
            continue
        have = [_num(r.get(name)) for r in reference]
        vals = [v for v in have if v is not None]
        if len(vals) >= _MIN_COVERAGE * len(reference):
            names.append(name)
    stats: dict[str, tuple[float, float]] = {}
    for name in names:
        vals = [v for v in (_num(r.get(name)) for r in reference) if v is not None]
        mean = sum(vals) / len(vals)
        std = math.sqrt(sum((v - mean) ** 2 for v in vals) / len(vals))
        if std > 0:
            stats[name] = (mean, std)
    if not stats:
        return unknown("no usable features", len(reference))
    cols = list(stats)

    def vec(row: dict[str, Any]) -> list[float]:
        out = []
        for c in cols:
            v = _num(row.get(c))
            out.append((v - stats[c][0]) / stats[c][1] if v is not None else 0.0)   # missing -> reference mean
        return out

    ref = [vec(r) for r in reference]
    cur = vec(current)

    def dist(a: list[float], b: list[float]) -> float:
        return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))

    base = [_mean_knn([dist(ref[i], ref[j]) for j in range(len(ref)) if j != i], k) for i in range(len(ref))]
    typical = sum(base) / len(base)
    if typical <= 0:
        return unknown("reference has no spread", len(reference), len(cols))
    ratio = _mean_knn([dist(cur, r) for r in ref], k) / typical
    return {"status": "ok", "ratio": ratio, "novelty_high": ratio >= ratio_threshold,
            "n_reference": len(reference), "n_features": len(cols)}
