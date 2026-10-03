"""Reliability map for the forecast LLM's stated confidence (logic-audit B1).

The forecast LLM states a `confidence`. The Trade Score then uses that raw number as
P(win) in its EV term, as a vote in the confluence ledger, and (via the tier) as a size
scale -- and nothing ever checked what "0.8" has actually meant. The only recalibration
was after the fact (Brier / accuracy as a pass-fail gate). This module learns, from closed
trades, what each stated-confidence bucket really delivered, so the EV term can use a
calibrated probability instead of the raw one.

**Where the data comes from.** `calibration_entries` does not store the stated confidence,
but it stores the Brier score and whether the call was directionally right, and
`compute_brier_score` is `(confidence - hit) ** 2` for long / short calls (`hit` = 1 when
the direction was right). So the stated confidence is recoverable exactly:
`confidence = 1 - sqrt(brier)` for a hit, `sqrt(brier)` for a miss. Neutral calls (a fixed
0.5) carry no information and are skipped.

**Design.** Fixed-width buckets over [0, 1]. A bucket with fewer than `min_samples`
observations is not trusted: `calibrate` returns the raw confidence for it. A trusted
bucket's hit rate is shrunk toward the raw confidence by `min_samples` pseudo-observations,
so a bucket that has only just crossed the floor cannot swing the score on a handful of
trades. Pure functions, no I/O, never raises on odd input.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

DEFAULT_BUCKET_WIDTH = 0.1
DEFAULT_MIN_SAMPLES = 30


@dataclass(frozen=True)
class BucketStat:
    lo: float
    hi: float
    n: int
    hits: int

    @property
    def hit_rate(self) -> float | None:
        return self.hits / self.n if self.n else None


@dataclass
class ReliabilityMap:
    buckets: list[BucketStat] = field(default_factory=list)
    n_pairs: int = 0
    bucket_width: float = DEFAULT_BUCKET_WIDTH
    min_samples: int = DEFAULT_MIN_SAMPLES

    def bucket_for(self, confidence: float) -> BucketStat | None:
        for b in self.buckets:
            if b.lo <= confidence < b.hi or (b.hi >= 1.0 and confidence == 1.0):
                return b
        return None

    def to_dict(self) -> dict[str, Any]:
        return {
            "n_pairs": self.n_pairs, "bucket_width": self.bucket_width, "min_samples": self.min_samples,
            "buckets": [{"lo": b.lo, "hi": b.hi, "n": b.n, "hits": b.hits, "hit_rate": b.hit_rate} for b in self.buckets],
        }


@dataclass(frozen=True)
class CalibratedConfidence:
    raw: float
    calibrated: float
    source: str          # "calibrated" | "raw_insufficient_sample" | "raw_no_map" | "raw_invalid"
    n_bucket: int = 0
    bucket_hit_rate: float | None = None

    def describe(self) -> str:
        if self.source == "calibrated":
            return (f"calibrated_confidence={self.calibrated:.2f} (raw={self.raw:.2f}; bucket n={self.n_bucket}, "
                    f"realized hit-rate={self.bucket_hit_rate:.2f})")
        return f"calibrated_confidence={self.calibrated:.2f} (raw={self.raw:.2f}; {self.source}, bucket n={self.n_bucket})"


def recover_pairs(entries: Iterable[Any]) -> list[tuple[float, bool]]:
    """(stated confidence, hit) for every long / short calibration entry. Entries whose Brier score is
    outside [0, 1] (corrupt) and neutral calls are skipped."""
    pairs: list[tuple[float, bool]] = []
    for e in entries:
        direction = getattr(e, "forecast_direction", None)
        if direction not in ("long", "short"):
            continue
        try:
            brier = float(e.brier_score)
            hit = bool(e.directional_correct)
        except (TypeError, ValueError, AttributeError):
            continue
        if not (0.0 <= brier <= 1.0) or math.isnan(brier):
            continue
        root = math.sqrt(brier)
        conf = 1.0 - root if hit else root
        pairs.append((min(1.0, max(0.0, conf)), hit))
    return pairs


def build_reliability_map(
    pairs: Iterable[tuple[float, bool]],
    *,
    bucket_width: float = DEFAULT_BUCKET_WIDTH,
    min_samples: int = DEFAULT_MIN_SAMPLES,
) -> ReliabilityMap:
    if not (0.0 < bucket_width <= 1.0):
        raise ValueError(f"bucket_width must be in (0, 1], got {bucket_width}")
    n_buckets = int(round(1.0 / bucket_width))
    counts = [[0, 0] for _ in range(n_buckets)]
    total = 0
    for conf, hit in pairs:
        if conf is None or math.isnan(conf):
            continue
        idx = min(n_buckets - 1, max(0, int(conf / bucket_width + 1e-9)))
        counts[idx][0] += 1
        counts[idx][1] += 1 if hit else 0
        total += 1
    buckets = [
        BucketStat(lo=round(i * bucket_width, 6), hi=round((i + 1) * bucket_width, 6), n=n, hits=h)
        for i, (n, h) in enumerate(counts)
    ]
    return ReliabilityMap(buckets=buckets, n_pairs=total, bucket_width=bucket_width, min_samples=min_samples)


def calibrate(raw: float, rmap: ReliabilityMap | None) -> CalibratedConfidence:
    """Calibrated probability for a stated `raw` confidence. Falls back to `raw` -- never invents a number --
    when there is no map, the input is not a probability, or the raw value's bucket is below the sample floor."""
    try:
        r = float(raw)
    except (TypeError, ValueError):
        return CalibratedConfidence(raw=0.0, calibrated=0.0, source="raw_invalid")
    if math.isnan(r) or not (0.0 <= r <= 1.0):
        return CalibratedConfidence(raw=r, calibrated=r, source="raw_invalid")
    if rmap is None or not rmap.buckets:
        return CalibratedConfidence(raw=r, calibrated=r, source="raw_no_map")
    b = rmap.bucket_for(r)
    if b is None or b.n < rmap.min_samples:
        return CalibratedConfidence(raw=r, calibrated=r, source="raw_insufficient_sample", n_bucket=b.n if b else 0)
    k = rmap.min_samples
    shrunk = (b.hits + k * r) / (b.n + k)
    return CalibratedConfidence(
        raw=r, calibrated=min(1.0, max(0.0, shrunk)), source="calibrated", n_bucket=b.n, bucket_hit_rate=b.hit_rate,
    )
