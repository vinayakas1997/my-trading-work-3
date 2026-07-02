"""Row column extractors."""

from __future__ import annotations


def col(rows: list[dict], key: str) -> list[float]:
    return [float(r[key]) for r in rows]
