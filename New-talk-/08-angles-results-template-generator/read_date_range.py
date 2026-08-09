"""Reads date-range.txt so every stage script shares the same real window
instead of each one picking its own via fetch_candles(limit=N)."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

_PATH = Path(__file__).parent / "date-range.txt"


def read_date_range() -> dict[str, int]:
    """Returns real UTC epoch seconds: {"start_ts", "end_ts", "chronos_kronos_end_ts"}."""
    values: dict[str, str] = {}
    for line in _PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()

    def to_ts(date_str: str) -> int:
        return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())

    return {
        "start_ts": to_ts(values["start_date"]),
        "end_ts": to_ts(values["end_date"]),
        "chronos_kronos_end_ts": to_ts(values["chronos_kronos_end_date"]),
        "news_start_ts": to_ts(values["news_start_date"]),
        "news_end_ts": to_ts(values["news_end_date"]),
    }


if __name__ == "__main__":
    print(read_date_range())
