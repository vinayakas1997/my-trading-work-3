from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from vinu_research.models import Hypothesis, HypothesisStatus

LOG = logging.getLogger(__name__)

HYPOTHESES_DIR = Path.home() / ".vinu"
HYPOTHESES_PATH = HYPOTHESES_DIR / "hypotheses.json"


class HypothesisRegistry:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or HYPOTHESES_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if not self._path.exists():
            return {"schema_version": "0.1", "hypotheses": {}}
        try:
            raw = self._path.read_text(encoding="utf-8")
            return json.loads(raw)
        except (json.JSONDecodeError, OSError) as exc:
            LOG.warning("Failed to load hypotheses from %s: %s", self._path, exc)
            return {"schema_version": "0.1", "hypotheses": {}}

    def _write(self, data: dict[str, Any]) -> None:
        tmp = None
        try:
            fd, tmp = tempfile.mkstemp(
                suffix=".tmp",
                prefix="hypotheses_",
                dir=str(self._path.parent),
            )
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_EX)
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(fd)
                fcntl.flock(f, fcntl.LOCK_UN)
            os.replace(tmp, str(self._path))
        except Exception as exc:
            LOG.error("Failed to write hypotheses to %s: %s", self._path, exc)
            raise
        finally:
            if tmp is not None and os.path.exists(tmp):
                try:
                    os.unlink(tmp)
                except OSError:
                    pass

    def _to_dict(self, h: Hypothesis) -> dict[str, Any]:
        return {
            "hypothesis_id": h.hypothesis_id,
            "title": h.title,
            "thesis": h.thesis,
            "status": h.status.value,
            "universe": h.universe,
            "signal_definition": h.signal_definition,
            "run_cards": h.run_cards,
            "created_at": h.created_at,
            "updated_at": h.updated_at,
        }

    def _from_dict(self, d: dict[str, Any]) -> Hypothesis:
        return Hypothesis(
            hypothesis_id=d["hypothesis_id"],
            title=d["title"],
            thesis=d["thesis"],
            status=HypothesisStatus(d["status"]),
            universe=list(d.get("universe", [])),
            signal_definition=d.get("signal_definition", ""),
            run_cards=list(d.get("run_cards", [])),
            created_at=d.get("created_at", ""),
            updated_at=d.get("updated_at", ""),
        )

    def create(self, hypothesis: Hypothesis) -> Hypothesis:
        data = self._load()
        hypotheses = data["hypotheses"]
        if hypothesis.hypothesis_id in hypotheses:
            raise ValueError(f"Hypothesis {hypothesis.hypothesis_id} already exists")
        hypotheses[hypothesis.hypothesis_id] = self._to_dict(hypothesis)
        self._write(data)
        return hypothesis

    def get(self, hypothesis_id: str) -> Hypothesis | None:
        data = self._load()
        raw = data["hypotheses"].get(hypothesis_id)
        if raw is None:
            return None
        return self._from_dict(raw)

    def update(self, hypothesis: Hypothesis) -> Hypothesis:
        data = self._load()
        if hypothesis.hypothesis_id not in data["hypotheses"]:
            raise KeyError(f"Hypothesis {hypothesis.hypothesis_id} not found")
        data["hypotheses"][hypothesis.hypothesis_id] = self._to_dict(hypothesis)
        self._write(data)
        return hypothesis

    def delete(self, hypothesis_id: str) -> bool:
        data = self._load()
        if hypothesis_id not in data["hypotheses"]:
            return False
        del data["hypotheses"][hypothesis_id]
        self._write(data)
        return True

    def list_all(
        self,
        status: HypothesisStatus | None = None,
    ) -> list[Hypothesis]:
        data = self._load()
        hypotheses = data["hypotheses"]
        result = [self._from_dict(v) for v in hypotheses.values()]
        if status is not None:
            result = [h for h in result if h.status == status]
        return sorted(result, key=lambda h: h.created_at, reverse=True)

    def link_backtest(self, hypothesis_id: str, run_card_path: str) -> Hypothesis | None:
        data = self._load()
        raw = data["hypotheses"].get(hypothesis_id)
        if raw is None:
            LOG.warning("Cannot link backtest: hypothesis %s not found", hypothesis_id)
            return None
        if run_card_path not in raw["run_cards"]:
            raw["run_cards"].append(run_card_path)
        raw["updated_at"] = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
        self._write(data)
        return self._from_dict(raw)

    def search(self, query: str) -> list[Hypothesis]:
        q = query.lower()
        data = self._load()
        result: list[Hypothesis] = []
        for raw in data["hypotheses"].values():
            h = self._from_dict(raw)
            if q in h.title.lower() or q in h.thesis.lower() or q in h.signal_definition.lower():
                result.append(h)
        return result

    def count(self) -> int:
        data = self._load()
        return len(data["hypotheses"])
