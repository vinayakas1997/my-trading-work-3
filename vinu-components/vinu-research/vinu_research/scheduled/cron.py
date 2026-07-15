from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone


def parse_cron(expr: str) -> dict[str, list[int]]:
    fields = expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Invalid cron expression: {expr}. Expected 5 fields.")

    names = ["minute", "hour", "day_of_month", "month", "day_of_week"]
    ranges = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]
    result: dict[str, list[int]] = {}

    for name, field, (lo, hi) in zip(names, fields, ranges):
        values: list[int] = []
        for part in field.split(","):
            if "/" in part:
                base, step = part.split("/")
                step = int(step)
                if base == "*":
                    values.extend(range(lo, hi + 1, step))
                elif "-" in base:
                    a, b = base.split("-")
                    values.extend(range(int(a), int(b) + 1, step))
                else:
                    start = int(base)
                    values.extend(range(start, hi + 1, step))
            elif part == "*":
                values.extend(range(lo, hi + 1))
            elif "-" in part:
                a, b = part.split("-")
                values.extend(range(int(a), int(b) + 1))
            else:
                values.append(int(part))
        result[name] = sorted(set(values))
    return result


def _py_weekday_to_cron(py_dow: int) -> int:
    return (py_dow + 1) % 7


def next_run(cron_expr: str, after: datetime | None = None) -> datetime:
    parsed = parse_cron(cron_expr)
    now = (after or datetime.now(timezone.utc)).replace(second=0, microsecond=0)
    for _ in range(525600):
        if now.minute in parsed["minute"] and \
           now.hour in parsed["hour"] and \
           now.day in parsed["day_of_month"] and \
           now.month in parsed["month"] and \
           _py_weekday_to_cron(now.weekday()) in parsed["day_of_week"]:
            return now
        now += timedelta(minutes=1)
    raise ValueError(f"No future match found for cron: {cron_expr}")
