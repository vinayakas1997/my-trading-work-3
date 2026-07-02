"""Z-score normalization for feature matrices."""

from __future__ import annotations

import math


def zscore_column(values: list[float | None]) -> list[float | None]:
    nums = [v for v in values if v is not None and not math.isnan(v)]
    if len(nums) < 2:
        return values
    mean = sum(nums) / len(nums)
    var = sum((x - mean) ** 2 for x in nums) / len(nums)
    std = math.sqrt(var) if var > 0 else 1.0
    out: list[float | None] = []
    for v in values:
        if v is None or math.isnan(v):
            out.append(None)
        else:
            out.append((v - mean) / std)
    return out
