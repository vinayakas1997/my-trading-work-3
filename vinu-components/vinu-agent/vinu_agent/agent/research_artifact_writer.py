"""Turns a `research` team's own PASS verdict into a real vinu-research
Artifact -- closing the gap where a PASS previously had no effect on
anything: OrderGuard's active-artifact check reads vinu-research's real
strategy_store.db, and nothing ever wrote to it from vinu-agent's side.

Written at status BENCHING, not ACTIVE -- research's 3-specialist team
(idea_generator -> backtest_runner -> risk_critic) is real but simpler
than vinu-research's own full promotion bar (deflated Sharpe ratio,
out-of-sample holdout, stress test, correlation gate). Marking it ACTIVE
here would be a stronger claim than this team's own rigor supports;
BENCHING means "real, tracked, not yet promoted" -- an honest state,
not a shortcut. Promoting BENCHING -> ACTIVE is a separate, later step
(vinu-research's own promotion tooling, or a future capital_allocator).

Best-effort throughout, matching broker/debrief.py's own documented
contract: any failure here is logged and swallowed, never raised -- this
must never break the research team's own primary result.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

LOG = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(content: str) -> Optional[dict[str, Any]]:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        LOG.warning("research manager's trailing json block did not parse")
        return None


def write_artifact_from_research_pass(
    content: str,
    *,
    strategy_store: Any,
    source_run_id: str = "",
) -> Optional[str]:
    """Returns the new artifact_id if one was written, None otherwise
    (verdict wasn't PASS, the json block was missing/unparseable, or the
    write itself failed) -- never raises."""
    try:
        data = _extract_json_block(content)
        if not data or data.get("verdict") != "PASS":
            return None

        symbol = str(data.get("symbol", "")).strip().upper()
        strategy_code = str(data.get("strategy_code", "")).strip()
        if not symbol or not strategy_code:
            LOG.warning(
                "research PASS json block missing symbol/strategy_code, skipping artifact write"
            )
            return None

        from vinu_research.models import Artifact, ArtifactStatus

        name = f"{symbol}-research-{source_run_id or 'manual'}"

        # Idempotency guard: if this run's TeamManager hook ever fires twice
        # for the same PASS verdict (a retried delegation, the hook getting
        # invoked again after a downstream failure), name is the same
        # deterministic (symbol, source_run_id) key both times. Without this
        # check, each call created a brand-new artifact_id (Artifact.create()
        # doesn't dedup on its own) -- two BENCHING artifacts for one real
        # research result, both visible to OrderGuard's active-artifact scan.
        existing = [
            a for a in strategy_store.list_artifacts_for_symbol(symbol)
            if a.name == name
        ]
        if existing:
            LOG.info(
                "research-pass artifact for %s already exists (%s), reusing instead of creating a duplicate",
                name, existing[0].artifact_id,
            )
            return existing[0].artifact_id

        artifact = Artifact.create("strategy", name, universe=[symbol])
        artifact.status = ArtifactStatus.BENCHING
        artifact.strategy_code = strategy_code
        artifact.initial_sharpe = float(data.get("sharpe", 0.0) or 0.0)
        artifact.initial_max_dd = float(data.get("max_drawdown", 0.0) or 0.0)
        # Real angle attribution -- only ever what the manager itself
        # reported using, never inferred/guessed here. Missing/malformed
        # is silently an empty list (no per-angle calibration for this
        # artifact), not an error -- most research passes won't report
        # this until teams/research/manager_prompt.md's own instruction is
        # actually followed consistently.
        angles_used = data.get("angles_used")
        if isinstance(angles_used, list):
            artifact.origin_angles = [str(a).strip() for a in angles_used if str(a).strip()]
        # source_run_id on the real Artifact model is an int (a vinu-research
        # backtest run id) -- vinu-agent's own run_id is a hex string from a
        # different id space, so it doesn't fit that field. The real link
        # back to this run lives in team_runs (run_id is the primary key
        # there already), not duplicated onto the artifact itself.

        strategy_store.upsert_artifact(artifact)
        return artifact.artifact_id
    except Exception:
        LOG.exception("failed to write research-pass artifact, continuing without it")
        return None


def write_artifacts_from_top3(
    candidates: list[dict[str, Any]],
    *,
    strategy_store: Any,
    symbol: str,
    source_run_id: str = "",
    top_n: int = 3,
) -> list[str]:
    """Write 9 not 1 (09 step2): top3 per interval (1d,1H,15min).

    `candidates` each has interval/code/sharpe/max_drawdown/angles_used.
    Upstream comparison.diverse_top_n already ensures best per shape.
    Caps top_n per interval, BENCHING, idempotent by name, never raises.
    """
    import os as _os

    try:
        _top = int(_os.environ.get("VINU_SWEEP_TOP_N", str(top_n)))
    except ValueError:
        _top = top_n
    ids: list[str] = []
    try:
        from vinu_research.models import Artifact, ArtifactStatus

        sym = symbol.strip().upper()
        by_interval: dict[str, list[dict[str, Any]]] = {}
        for c in candidates:
            by_interval.setdefault(str(c.get("interval", "1d")), []).append(c)
        for interval, items in by_interval.items():
            for rank, c in enumerate(items[:_top], start=1):
                code = str(c.get("strategy_code", "")).strip()
                if not code:
                    continue
                name = f"{sym}-{interval}-top{rank}-{source_run_id or 'manual'}"
                existing = [a for a in strategy_store.list_artifacts_for_symbol(sym) if a.name == name]
                if existing:
                    ids.append(existing[0].artifact_id)
                    continue
                a = Artifact.create("strategy", name, universe=[sym])
                a.status = ArtifactStatus.BENCHING
                a.strategy_code = code
                a.initial_sharpe = float(c.get("sharpe", 0.0) or 0.0)
                a.initial_max_dd = float(c.get("max_drawdown", 0.0) or 0.0)
                angles = c.get("angles_used")
                if isinstance(angles, list):
                    a.origin_angles = [str(x).strip() for x in angles if str(x).strip()]
                strategy_store.upsert_artifact(a)
                ids.append(a.artifact_id)
        return ids
    except Exception:
        LOG.exception("failed to write top3 artifacts, continuing without them")
        return ids
