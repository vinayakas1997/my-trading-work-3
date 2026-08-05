"""Method 3 — Velocity Spike / News-Volume Anomaly Detection.

Spec: New-talk-/Final-implementation/01-present-considerations/03-velocity-spike-anomaly-detection.md

Build call: **build new**. Nothing in `vinu-news` currently tracks
article *counts* over rolling time buckets per category/ticker — this is
pure counting/arithmetic on already-available article metadata
(`category`, `sort_ts`), no existing module to adapt.

Input: not a single article — a set of articles bucketed by category (or
ticker) and time window. This module takes that bucketing as a plain
list of `(group_key, unix_ts)` pairs (or a list of article dicts with a
`group_key_fn`/`ts_key`) rather than owning storage of a rolling
168-hour history — the spec notes this project doesn't currently persist
that anywhere ("would need a small new table"); building that persistence
layer is out of scope for a stateless `compute()`-shaped method module,
so the z-score path here accepts a caller-supplied rolling count series
instead of reading/writing its own table.

Output: ratio version -> `{"velocity_spike": bool, "severity": "medium"|
"high"|None, "ratio": float}`. Z-score version -> `{"deviation": bool,
"severity": "medium"|"high"|"critical"|None, "z_score": float}`.
"""

from __future__ import annotations

import statistics
from collections import defaultdict

RATIO_SPIKE_THRESHOLD = 3.0
RATIO_MIN_RECENT = 5
RATIO_HIGH_SEVERITY = 5.0

ZSCORE_DEVIATION_THRESHOLD = 2.0
ZSCORE_HIGH_SEVERITY = 3.0
ZSCORE_CRITICAL_SEVERITY = 4.0
ZSCORE_MIN_SAMPLE_SIZE = 24
ZSCORE_MIN_STDDEV = 0.5


def bucket_hourly_counts(
    items: list[dict], ts_key: str = "sort_ts", group_key: str = "category"
) -> dict[str, dict[int, int]]:
    """Bucket article metadata into per-group, per-hour counts.

    `items` is a list of dicts each containing at least `ts_key` (unix
    seconds) and `group_key` (e.g. category or ticker string). Returns
    `{group_value: {hour_bucket: count}}` where `hour_bucket` is the
    unix timestamp floored to the hour.
    """
    buckets: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for item in items:
        group_value = item[group_key]
        hour_bucket = int(item[ts_key]) // 3600 * 3600
        buckets[group_value][hour_bucket] += 1
    return {group: dict(hours) for group, hours in buckets.items()}


def detect_velocity_spike(recent_count: int, older_count: int) -> dict:
    """Ratio-based spike detection: 'last hour' vs 'the hour before that'."""
    ratio = recent_count / max(older_count, 1)
    spike = ratio >= RATIO_SPIKE_THRESHOLD and recent_count >= RATIO_MIN_RECENT
    severity = None
    if spike:
        severity = "high" if ratio >= RATIO_HIGH_SEVERITY else "medium"
    return {"velocity_spike": spike, "severity": severity, "ratio": round(ratio, 4)}


def detect_zscore_deviation(history_counts: list[float], current_count: float) -> dict:
    """Rolling z-score deviation over a (up to 168-hour) history of hourly counts.

    `history_counts` should be the prior window (e.g. up to 168 hourly
    counts), not including `current_count`.
    """
    sample_size = len(history_counts)
    if sample_size < ZSCORE_MIN_SAMPLE_SIZE:
        return {"deviation": False, "severity": None, "z_score": 0.0}

    mean = statistics.mean(history_counts)
    stddev = statistics.pstdev(history_counts)
    if stddev < ZSCORE_MIN_STDDEV:
        return {"deviation": False, "severity": None, "z_score": 0.0}

    z_score = (current_count - mean) / stddev
    deviation = z_score >= ZSCORE_DEVIATION_THRESHOLD
    severity = None
    if deviation:
        if z_score >= ZSCORE_CRITICAL_SEVERITY:
            severity = "critical"
        elif z_score >= ZSCORE_HIGH_SEVERITY:
            severity = "high"
        else:
            severity = "medium"
    return {"deviation": deviation, "severity": severity, "z_score": round(z_score, 4)}
