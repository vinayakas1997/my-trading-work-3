import json
from pathlib import Path
from typing import Dict, Optional

from .models import RunStatus, SwarmRun


class SwarmStore:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _run_path(self, run_id: str) -> Path:
        return self.base_dir / f"{run_id}.json"

    def save(self, run: SwarmRun) -> None:
        path = self._run_path(run.run_id)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(run.to_dict(), indent=2, default=str))
        tmp.rename(path)

    def get(self, run_id: str) -> Optional[SwarmRun]:
        path = self._run_path(run_id)
        if not path.exists():
            return None
        return SwarmRun.from_dict(json.loads(path.read_text()))

    def list(self, limit: int = 20) -> list:
        runs = []
        for p in sorted(self.base_dir.glob("*.json"), reverse=True)[:limit]:
            runs.append(SwarmRun.from_dict(json.loads(p.read_text())))
        return runs

    def find_latest_run(
        self, preset_name: str, symbol: str, status: RunStatus = RunStatus.COMPLETED,
    ) -> Optional[SwarmRun]:
        """Most recent run matching preset_name + user_vars["symbol"] + status,
        by `created_at` (a real ISO timestamp) -- NOT `list()`'s filename sort,
        which is unreliable here since run_id is a random uuid hex, not
        time-ordered. Scans every run file (no `limit` cap, unlike `list()`)
        since a symbol's debate could be older than the last 20 runs across
        all presets/symbols. Used by trade-plan authoring (a different
        service, over HTTP) to opportunistically fold a completed
        investment_committee debate into the signal ledger -- see
        routes_swarm.py's `/swarm/runs/latest` route."""
        best: Optional[SwarmRun] = None
        for p in self.base_dir.glob("*.json"):
            try:
                run = SwarmRun.from_dict(json.loads(p.read_text()))
            except (json.JSONDecodeError, OSError):
                continue
            if run.preset_name != preset_name or run.status != status:
                continue
            if run.user_vars.get("symbol", "").upper() != symbol.upper():
                continue
            if best is None or run.created_at > best.created_at:
                best = run
        return best

    def update_status(self, run_id: str, status: RunStatus, final_report: str = "", error: Optional[str] = None) -> None:
        run = self.get(run_id)
        if run:
            run.status = status
            if final_report:
                run.final_report = final_report
            if error:
                run.error = error
            self.save(run)
