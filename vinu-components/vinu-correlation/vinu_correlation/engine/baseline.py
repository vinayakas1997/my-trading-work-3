from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_baseline(
    articles: list[dict],
    window_days: int = 7,
    session_aware: bool = True,
) -> list[dict[str, Any]]:
    from vinu_correlation.engine.market_hours import classify_session

    hourly_counts: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for a in articles:
        ts = a.get("sort_ts", a.get("ts", 0))
        if not ts:
            continue
        hour_bucket = (ts // 3600) * 3600
        session = classify_session(ts).name if session_aware else "regular"
        hourly_counts[hour_bucket][session] += 1

    if not hourly_counts:
        return []

    min_ts = min(hourly_counts.keys())
    window_sec = window_days * 86400

    baselines = []
    for hour_ts, sessions in sorted(hourly_counts.items()):
        window_start = hour_ts - window_sec
        for session_name in set(sessions.keys()) | {"regular", "pre_market", "after_hours"}:
            counts_in_window = [
                sc.get(session_name, 0)
                for ht, sc in hourly_counts.items()
                if window_start <= ht < hour_ts
            ]
            current_count = sessions.get(session_name, 0)
            if not counts_in_window:
                mean = float(current_count)
                stddev = 1.0
            else:
                mean = sum(counts_in_window) / len(counts_in_window)
                variance = sum((c - mean) ** 2 for c in counts_in_window) / len(counts_in_window)
                stddev = variance ** 0.5 or 1.0

            z_score = (current_count - mean) / stddev
            deviation_level = _classify_deviation(z_score)

            baselines.append({
                "symbol": "",
                "hour_ts": hour_ts,
                "session": session_name,
                "article_count": current_count,
                "mean": round(mean, 4),
                "stddev": round(stddev, 4),
                "sample_size": len(counts_in_window),
            })

    return baselines


def classify_deviation(z_score: float) -> str:
    return _classify_deviation(z_score)


def _classify_deviation(z_score: float) -> str:
    abs_z = abs(z_score)
    if abs_z > 4:
        return "critical"
    elif abs_z > 3:
        return "high"
    elif abs_z > 2:
        return "elevated"
    return "normal"
