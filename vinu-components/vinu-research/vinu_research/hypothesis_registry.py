from __future__ import annotations

import json
import logging
import os
import tempfile
from pathlib import Path
from typing import Any

from vinu_infra.debug import debug_log
from vinu_research.models import Evidence, Hypothesis, HypothesisStatus

LOG = logging.getLogger(__name__)

# In Docker, research-api's container is read_only: true with only /data
# (bind-mounted from ./data/research) and tmpfs writable -- Path.home()
# resolves to a non-writable, sometimes nonexistent path there (confirmed:
# `/nonexistent`, this environment's HOME for a container user with no
# real passwd entry), so every one of this module's ~11 no-arg
# `HypothesisRegistry()` call sites (service.py, routes_hypothesis.py,
# routes_introspect.py, tools.py, cli.py) crashed with
# `OSError: [Errno 30] Read-only file system` the first time a real
# /research/run actually reached this code path. Respecting
# VINU_RESEARCH_DATA_ROOT here -- the same env var vinu_research/config.py
# already uses for its own data root -- fixes all of them from this one
# place; Path.home() remains the fallback for host-mode (non-Docker) use
# where that var isn't set.
_data_root_env = os.environ.get("VINU_RESEARCH_DATA_ROOT", "").strip()
HYPOTHESES_DIR = Path(_data_root_env) if _data_root_env else (Path.home() / ".vinu")
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
            debug_log(f"_load: loaded {len(raw)} bytes from {self._path}", level=2)
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
            # No file lock needed: the temp file is private to this process and
            # atomicity comes from os.replace below. (The previous fcntl.flock
            # was Unix-only and locked only the private temp file anyway.)
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
                f.flush()
                os.fsync(fd)
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
            "strategy_type": h.strategy_type,
            "indicators_used": h.indicators_used,
            "params_tested": h.params_tested,
            "evidence": [
                {
                    "run_id": e.run_id,
                    "iteration": e.iteration,
                    "metric": e.metric,
                    "value": e.value,
                    "conclusion": e.conclusion,
                    "reasoning": e.reasoning,
                    "timestamp": e.timestamp,
                    "metrics_snapshot": e.metrics_snapshot,
                    "report_path": e.report_path,
                }
                for e in h.evidence
            ],
            "invalidation_reason": h.invalidation_reason,
            "best_sharpe": h.best_sharpe,
            "created_at": h.created_at,
            "updated_at": h.updated_at,
        }

    def _from_dict(self, d: dict[str, Any]) -> Hypothesis:
        evidence_list = []
        for e in d.get("evidence", []):
            if isinstance(e, dict):
                evidence_list.append(Evidence(
                    run_id=e.get("run_id", 0),
                    iteration=e.get("iteration", 0),
                    metric=e.get("metric", ""),
                    value=e.get("value", 0.0),
                    conclusion=e.get("conclusion", ""),
                    reasoning=e.get("reasoning", ""),
                    timestamp=e.get("timestamp", ""),
                    metrics_snapshot=e.get("metrics_snapshot"),
                    report_path=e.get("report_path"),
                ))
        return Hypothesis(
            hypothesis_id=d["hypothesis_id"],
            title=d["title"],
            thesis=d["thesis"],
            status=HypothesisStatus(d["status"]),
            universe=list(d.get("universe", [])),
            signal_definition=d.get("signal_definition", ""),
            run_cards=list(d.get("run_cards", [])),
            strategy_type=d.get("strategy_type", ""),
            indicators_used=list(d.get("indicators_used", [])),
            params_tested=dict(d.get("params_tested", {})),
            evidence=evidence_list,
            invalidation_reason=d.get("invalidation_reason"),
            best_sharpe=float(d.get("best_sharpe", 0.0)),
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

    def add_evidence(self, hypothesis_id: str, evidence: Evidence) -> Hypothesis | None:
        data = self._load()
        raw = data["hypotheses"].get(hypothesis_id)
        if raw is None:
            LOG.warning("Cannot add evidence: hypothesis %s not found", hypothesis_id)
            return None
        h = self._from_dict(raw)
        h.evidence.append(evidence)
        if evidence.value > h.best_sharpe:
            h.best_sharpe = evidence.value
        if h.status == HypothesisStatus.rejected:
            LOG.warning(
                "Evidence added to rejected hypothesis %s — status unchanged",
                hypothesis_id,
            )
        else:
            if evidence.conclusion == "supports" and h.best_sharpe > 0.3:
                h.status = HypothesisStatus.testing if h.status == HypothesisStatus.exploring else h.status
            if evidence.conclusion == "supports" and h.best_sharpe > 0.5:
                h.status = HypothesisStatus.validated
        h.updated_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
        data["hypotheses"][hypothesis_id] = self._to_dict(h)
        self._write(data)
        return h

    def add_evidence_batch(self, hypothesis_id: str, evidence_list: list[Evidence]) -> Hypothesis | None:
        data = self._load()
        raw = data["hypotheses"].get(hypothesis_id)
        if raw is None:
            LOG.warning("Cannot add evidence batch: hypothesis %s not found", hypothesis_id)
            return None
        h = self._from_dict(raw)
        debug_log(f"add_evidence_batch: {hypothesis_id} count={len(evidence_list)}", level=2)
        now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        for evidence in evidence_list:
            h.evidence.append(evidence)
            if evidence.value > h.best_sharpe:
                h.best_sharpe = evidence.value
            if h.status == HypothesisStatus.rejected:
                continue
            if evidence.conclusion == "supports" and h.best_sharpe > 0.3:
                h.status = HypothesisStatus.testing if h.status == HypothesisStatus.exploring else h.status
            if evidence.conclusion == "supports" and h.best_sharpe > 0.5:
                h.status = HypothesisStatus.validated
        h.updated_at = now
        data["hypotheses"][hypothesis_id] = self._to_dict(h)
        self._write(data)
        return h

    def reject_with_reason(self, hypothesis_id: str, reason: str) -> Hypothesis | None:
        data = self._load()
        raw = data["hypotheses"].get(hypothesis_id)
        if raw is None:
            LOG.warning("Cannot reject: hypothesis %s not found", hypothesis_id)
            return None
        h = self._from_dict(raw)
        debug_log(f"reject_with_reason: {hypothesis_id} reason={reason}", level=2)
        h.status = HypothesisStatus.rejected
        h.invalidation_reason = reason
        h.updated_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat()
        data["hypotheses"][hypothesis_id] = self._to_dict(h)
        self._write(data)
        return h

    def query_by_symbol(self, symbol: str, status: HypothesisStatus | None = None) -> list[Hypothesis]:
        data = self._load()
        result: list[Hypothesis] = []
        for raw in data["hypotheses"].values():
            h = self._from_dict(raw)
            if symbol.upper() in [s.upper() for s in h.universe]:
                if status is None or h.status == status:
                    result.append(h)
        return sorted(result, key=lambda h: h.updated_at, reverse=True)

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
