import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config import AgentConfig
from .models import RunStatus, SwarmRun, SwarmTask, TaskStatus
from .store import SwarmStore
from .worker import run_worker


_PRESETS_DIR = Path(__file__).parent / "presets"


class SwarmRuntime:
    def __init__(
        self,
        store: SwarmStore,
        services_config: Optional[dict] = None,
    ) -> None:
        self._store = store
        self._services_config = services_config or {}
        self._executor = ThreadPoolExecutor(max_workers=4)
        self._lock = threading.Lock()

    def list_presets(self) -> List[dict]:
        presets = []
        if _PRESETS_DIR.exists():
            for f in sorted(_PRESETS_DIR.glob("*.yaml")):
                presets.append({"name": f.stem, "file": f.name})
        return presets

    def get_preset(self, name: str) -> Optional[dict]:
        path = _PRESETS_DIR / f"{name}.yaml"
        if not path.exists():
            return None
        import yaml
        return yaml.safe_load(path.read_text())

    def create_run(self, preset_name: str, user_vars: Dict[str, str]) -> SwarmRun:
        preset = self.get_preset(preset_name)
        if not preset:
            raise ValueError(f"Preset '{preset_name}' not found")

        run = SwarmRun(
            preset_name=preset_name,
            user_vars=user_vars,
        )

        raw_tasks = preset.get("tasks", [])
        for raw in raw_tasks:
            prompt = raw.get("prompt", "")
            for key, val in user_vars.items():
                prompt = prompt.replace(f"{{{{{key}}}}}", val)
            task = SwarmTask(
                run_id=run.run_id,
                agent_name=raw.get("agent_name", "agent"),
                role=raw.get("role", "analyst"),
                prompt=prompt,
                depends_on=raw.get("depends_on", []),
            )
            run.tasks.append(task)

        self._store.save(run)
        return run

    def start_run(self, run_id: str) -> SwarmRun:
        run = self._store.get(run_id)
        if not run:
            raise ValueError(f"Run {run_id} not found")
        if run.status != RunStatus.PENDING:
            raise ValueError(f"Run {run_id} already started")

        run.status = RunStatus.RUNNING
        self._store.save(run)

        thread = threading.Thread(
            target=self._execute_dag,
            args=(run_id,),
            daemon=True,
        )
        thread.start()
        return run

    def get_run(self, run_id: str) -> Optional[SwarmRun]:
        return self._store.get(run_id)

    def cancel_run(self, run_id: str) -> bool:
        run = self._store.get(run_id)
        if not run or run.status != RunStatus.RUNNING:
            return False
        run.status = RunStatus.CANCELLED
        self._store.save(run)
        return True

    def _execute_dag(self, run_id: str) -> None:
        run = self._store.get(run_id)
        if not run:
            return

        task_map = {t.task_id: t for t in run.tasks}

        while not run.all_done():
            ready = run.get_ready_tasks()
            if not ready:
                if not run.all_done():
                    blocked = [t.task_id for t in run.tasks if t.status == TaskStatus.PENDING]
                    if blocked:
                        run.error = f"Stalled: blocked tasks {blocked}"
                        run.status = RunStatus.FAILED
                        self._store.save(run)
                break

            futures = {}
            for task in ready:
                task.status = TaskStatus.RUNNING
                task.started_at = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
                self._store.save(run)

                context_parts = []
                for dep_id in task.depends_on:
                    dep = task_map.get(dep_id)
                    if dep and dep.result:
                        context_parts.append(f"=== {dep.agent_name} ({dep.role}) ===\n{dep.result}")
                context = "\n\n".join(context_parts) if context_parts else None

                fut = self._executor.submit(
                    run_worker,
                    task_prompt=task.prompt,
                    agent_name=task.agent_name,
                    role=task.role,
                    context=context,
                    services_config=self._services_config,
                )
                futures[fut] = task

            for fut in as_completed(futures):
                task = futures[fut]
                try:
                    result = fut.result()
                    if result.get("status") == "error":
                        task.status = TaskStatus.FAILED
                        task.error = result.get("content", "Unknown error")
                    else:
                        task.status = TaskStatus.COMPLETED
                        task.result = result.get("content", "")
                except Exception as exc:
                    task.status = TaskStatus.FAILED
                    task.error = str(exc)
                task.completed_at = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
                self._store.save(run)

            run = self._store.get(run_id)
            if not run or run.status == RunStatus.CANCELLED:
                return

        run = self._store.get(run_id)
        if run and run.status != RunStatus.CANCELLED:
            failed = [t for t in run.tasks if t.status == TaskStatus.FAILED]
            if failed:
                run.status = RunStatus.FAILED
                run.error = f"{len(failed)} task(s) failed: {[t.agent_name for t in failed]}"
            else:
                run.status = RunStatus.COMPLETED
                run.final_report = self._synthesize_report(run)
            run.completed_at = __import__("time").strftime("%Y-%m-%dT%H:%M:%SZ", __import__("time").gmtime())
            self._store.save(run)

    def _synthesize_report(self, run: SwarmRun) -> str:
        parts = [f"# Swarm Report: {run.preset_name}\n"]
        for task in run.tasks:
            parts.append(f"## {task.agent_name} ({task.role})")
            parts.append(task.result[:2000] if task.result else "(no output)")
        return "\n\n".join(parts)
