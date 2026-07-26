from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class JudgmentRecord:
    ts: str
    symbol: str
    iteration: int
    verdict: str
    in_sample_sharpe: float
    out_of_sample_sharpe: float | None
    holdout_sharpe: float | None
    verdict_correct: bool | None
    llm_calls_used: int
    run_id: int = 0
    model: str = ""
    strategy_code_hash: str = ""


class JudgmentStore:
    def __init__(self, path: Path | str | None = None) -> None:
        self._records: list[JudgmentRecord] = []
        self._lock = threading.Lock()
        self._path = Path(path) if path else None

    def record(self, record: JudgmentRecord) -> None:
        with self._lock:
            self._records.append(record)
        if self._path:
            self._persist(record)

    def _persist(self, record: JudgmentRecord) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record.__dict__) + "\n")
        except OSError as exc:
            import logging
            logging.getLogger(__name__).warning("Failed to write judgment log: %s", exc)

    def load(self) -> None:
        if not self._path or not self._path.exists():
            return
        with self._lock:
            self._records.clear()
            for line in self._path.read_text(encoding="utf-8").strip().splitlines():
                if not line:
                    continue
                data = json.loads(line)
                self._records.append(JudgmentRecord(**data))

    @property
    def total_records(self) -> int:
        with self._lock:
            return len(self._records)

    def calibration_summary(self) -> dict[str, Any]:
        with self._lock:
            by_verdict: dict[str, list[bool | None]] = {}
            for r in self._records:
                if r.verdict_correct is not None:
                    by_verdict.setdefault(r.verdict, []).append(r.verdict_correct)
            summary: dict[str, Any] = {
                "total": len(self._records),
                "with_outcome": sum(1 for r in self._records if r.verdict_correct is not None),
            }
            accuracies: dict[str, dict[str, Any]] = {}
            for verdict, outcomes in by_verdict.items():
                correct = sum(1 for o in outcomes if o)
                total = len(outcomes)
                accuracies[verdict] = {
                    "count": total,
                    "correct": correct,
                    "accuracy": round(correct / total, 3) if total > 0 else 0.0,
                }
            summary["by_verdict"] = accuracies
            return summary

    def reset(self) -> None:
        with self._lock:
            self._records.clear()
