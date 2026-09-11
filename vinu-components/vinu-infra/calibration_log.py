"""Append-only observation log for judgment-call checkpoints -- the
Category C items in other-repos-world/research-discussion-v1/
the-resaoning-ineffciency/00-audit.md (thresholds picked by reasoning,
not measurement: the rebalance-protect gain threshold, the bracket
take-fraction, the thesis-duplicate similarity cutoff, ...).

This is NOT a decision store -- nothing reads it back to decide anything,
and writing to it never blocks or changes the real decision path (every
call site wraps `record()` in a best-effort try/except upstream, same
posture as `broker/kill_switch.py`'s `AuditLogger.log()`). It exists so
each of those threshold decisions leaves a record of what the system
decided and the exact numbers behind it, so the threshold can eventually
be checked against what actually happened (was this gain protected worth
protecting? did the position that got a 25% partial actually keep
running?) instead of staying an unvalidated guess forever.

Gated to when a real broker is connected (paper or live), by convention
at each call site -- recording synthetic/test-run decisions would pollute
the one thing that makes this data useful: that it only reflects real
trading circumstances the system was actually run under.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DEFAULT_LOG_PATH = os.environ.get(
    "VINU_CALIBRATION_LOG",
    os.environ.get("VINU_DATA_ROOT", str(Path.home() / ".vinu")) + "/calibration_log.jsonl",
)


def record(checkpoint: str, context: dict[str, Any], *, log_path: str | Path | None = None) -> None:
    """Append one observation. Best-effort: any failure here (permissions,
    disk full, a non-serializable value in context) is swallowed, never
    raised -- a calibration-data write must never be able to break a real
    trading decision, same contract as every other audit/log writer in
    this codebase."""
    try:
        path = Path(log_path) if log_path is not None else Path(DEFAULT_LOG_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"checkpoint": checkpoint, "timestamp": time.time(), **context}
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    except Exception:  # noqa: BLE001 -- best-effort, see docstring
        pass


def read_all(checkpoint: str | None = None, *, log_path: str | Path | None = None) -> list[dict[str, Any]]:
    """Read back everything recorded (optionally filtered to one
    checkpoint) -- for later offline calibration analysis, not for any
    live decision path. Missing file returns an empty list, not an error."""
    path = Path(log_path) if log_path is not None else Path(DEFAULT_LOG_PATH)
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if checkpoint is None or entry.get("checkpoint") == checkpoint:
                entries.append(entry)
    return entries
