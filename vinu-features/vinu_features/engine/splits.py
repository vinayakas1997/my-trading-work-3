"""Optional train/valid/test date boundaries (manifest metadata only in v1)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TimeSplitPreset:
    train_end_ts: int | None = None
    valid_end_ts: int | None = None

    def describe(self) -> str:
        parts = []
        if self.train_end_ts is not None:
            parts.append(f"train_end_ts={self.train_end_ts}")
        if self.valid_end_ts is not None:
            parts.append(f"valid_end_ts={self.valid_end_ts}")
        return ", ".join(parts) if parts else "(no split configured)"
