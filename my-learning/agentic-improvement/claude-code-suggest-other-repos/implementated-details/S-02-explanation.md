# S-02: Evidence-Artifact Linking — Explanation & Status

## What It Is

Links each evidence record to a quantitative metrics snapshot and an optional report path, bridging raw evidence text with measurable trading outcomes.

## Components

1. **`Evidence.metrics_snapshot` (`dict[str, float] | None`) and `report_path` (`str | None`)** — two optional fields added to the `Evidence` dataclass in `models.py`. `metrics_snapshot` stores structured metrics (sharpe, max_dd, etc.) and `report_path` links to a rendered artifact on disk.

2. **`loop.py` evidence loop** — populates `metrics_snapshot` with computed values: `sharpe`, `max_dd`, `trade_count`, `win_rate` — all drawn from the backtest result for the iteration being recorded.

3. **Serialization gap** — `_to_dict()` / `_from_dict()` in `hypothesis_registry.py` were initially missing these fields, causing silent data loss on every disk write. Fixed in a subsequent audit — both fields are now serialized and deserialized, preserving evidence-artifact links across restarts.

## Current Status: ✅ IMPLEMENTED

Evidence records carry full metrics context; serialization is lossless.
