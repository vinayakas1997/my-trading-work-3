"""Research-digest reader — the missing "how does the user/agent find out
what happened" piece. `vinu-research`'s `run_research()` now generates a
plain-English `summary_text` per run, but nothing pushes it anywhere; the
agent only learns about it if it happens to ask. This reader surfaces the
most recent unseen run summary per symbol, proactively, the next time that
symbol comes up in a session — the same "next natural touchpoint" pattern
`GroundTruthInjector`/`FactsRegistry`/`FreshnessChecker` already use, since
this system has no out-of-band push channel to a human outside a session.

Tracks "already seen" per symbol in a small persisted state file so the
same run's summary doesn't get repeated every single turn forever.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _load_state(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(path: Path, state: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state), encoding="utf-8")


class ResearchDigestReader:
    """Best-effort: any per-symbol fetch failure is skipped, not raised."""

    def __init__(self, services_config: dict | None = None, state_path: str | Path = "") -> None:
        self._services_config = services_config or {}
        self._state_path = Path(state_path) if state_path else None

    def check_symbols(self, symbols: list[str]) -> list[dict[str, Any]]:
        research_url = self._services_config.get("vinu_research")
        if not research_url or not symbols:
            return []

        seen = _load_state(self._state_path) if self._state_path else {}
        findings: list[dict[str, Any]] = []

        import httpx

        for symbol in sorted(set(s for s in symbols if s)):
            try:
                resp = httpx.get(
                    f"{research_url}/research/runs",
                    params={"symbol": symbol, "limit": 1},
                    timeout=5.0,
                )
                if resp.status_code != 200:
                    continue
                runs = resp.json()
            except Exception:
                logger.debug("ResearchDigestReader: fetch failed for %s", symbol, exc_info=True)
                continue

            if not isinstance(runs, list) or not runs:
                continue
            run = runs[0]
            if not isinstance(run, dict):
                continue

            run_id = run.get("id")
            summary_text = (run.get("summary_text") or "").strip()
            if run_id is None or not summary_text:
                continue

            if seen.get(symbol) == run_id:
                continue  # already surfaced this exact run to the agent

            findings.append({
                "symbol": symbol,
                "run_id": run_id,
                "summary_text": summary_text,
                "best_sharpe": run.get("best_sharpe"),
                "status": run.get("status"),
            })
            seen[symbol] = run_id

        if findings and self._state_path:
            _save_state(self._state_path, seen)

        return findings
