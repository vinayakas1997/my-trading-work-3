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

    def update_status(self, run_id: str, status: RunStatus, final_report: str = "", error: Optional[str] = None) -> None:
        run = self.get(run_id)
        if run:
            run.status = status
            if final_report:
                run.final_report = final_report
            if error:
                run.error = error
            self.save(run)
