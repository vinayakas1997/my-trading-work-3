from __future__ import annotations

from collections import defaultdict
from typing import Any


def compute_baseline(
    articles: list[dict],
    window_days: int = 7,
    session_aware: bool = True,
) -> list[dict[str, Any]]:
    from vinu_initial_analysis.angles._market_hours import classify_session

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

    sorted_hours = sorted(hourly_counts.items())
    window_sec = window_days * 86400
    
    all_sessions = set()
    for hour_ts, sessions in hourly_counts.items():
        all_sessions.update(sessions.keys())
    all_sessions.update({"london", "ny_premarket", "ny_regular", "ny_afterhours"})

    session_counts: dict[str, list[int]] = {}
    session_accums: dict[str, int] = {}
    for sn in all_sessions:
        session_counts[sn] = []
        session_accums[sn] = 0


    hour_keys = [h for h, _ in sorted_hours]
    left = 0

    baselines = []
    for hour_ts, sessions in sorted_hours:
        window_start = hour_ts - window_sec

        while left < len(hour_keys) and hour_keys[left] < window_start:
            for sn in all_sessions:
                session_accums[sn] -= session_counts[sn][left]
            left += 1

        for sn in all_sessions:
            session_counts[sn].append(sessions.get(sn, 0))
            session_accums[sn] += sessions.get(sn, 0)

        for session_name in set(sessions.keys()) | all_sessions:
            current_count = sessions.get(session_name, 0)
            n_in_window = len(session_counts[session_name]) - left
            total_in_window = session_accums[session_name]

            if n_in_window <= 1:
                mean = float(current_count)
                stddev = 1.0
            else:
                mean = total_in_window / n_in_window
                sq_diff = 0.0
                for i in range(left, len(session_counts[session_name]) - 1):
                    sq_diff += (session_counts[session_name][i] - mean) ** 2
                variance = sq_diff / (n_in_window - 1)
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
                "z_score": round(z_score, 4),
                "deviation_level": deviation_level,
                "sample_size": n_in_window,
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
