"""Analysis H, consistency piece -- runs `freeze_manifest`/
`contamination_check` (vinu_infra/freeze.py) on the worker's own schedule
instead of only when someone remembers to trigger it manually. Design
reference: missing-pieces-of-system/maturity-agentic-system/thinking-1/
02-decided-pattern/25-A-Y-details/05-governance-freshness.md ("H",
consistency piece).

**Verified, not assumed**: `freeze_manifest(output_path=None) -> dict` and
`contamination_check(old, new) -> dict` are plain functions, no CLI/
argparse/interactive-prompt dependency -- fully callable from a scheduled
worker with no changes to `freeze.py` itself. The design doc's framing of
this piece as "currently a one-off, manually-triggered" turned out wrong
once checked: grepping the whole tree found no caller anywhere (no CLI
wrapper, no existing manual trigger either) -- it was simply unused, not
manually-triggered.

**Scoping correction, real and load-bearing**: `freeze_manifest()` hashes
every `VINU_*_DATA_ROOT` env var and the files under each root, plus every
`VINU_*` env var -- a whole-environment drift/contamination check, not a
`strategy_family`-scoped "research-vs-live divergence" the design doc's
`signal_json` sketch (`{live_backtest_divergence, divergence_trend}`)
implies. No per-`strategy_family` breakdown is possible from what
`freeze_manifest`/`contamination_check` actually compute (confirmed: they
operate on global file hashes and env vars, nothing per-strategy) --
`strategy_family`'s "no such categorical concept exists anywhere" gap
already blocking analysis B doesn't even apply here, since this piece
never needed to join to it in the first place. Implemented as a single
`scope_type=system` finding instead, same "reuse what's real" scope-down
already applied to C/H (governance piece).

Also **not** a PSI-shaped metric -- `contamination_check()` returns a
structural diff (added/removed/changed file hashes, changed env vars),
not two comparable numeric distributions. Treated as a `domain_floor`
event (per `00-index.md`'s own allowance for that shape, already used the
same way by analysis A's Brier-score floor): any real drift is
`significant` on its own, regardless of a PSI computation that doesn't
apply here. Event-triggered by nature (only meaningful once a second
manifest exists to diff against the first) -- same `n/a`-trend caveat
already carried by N and H's governance piece.

Persistence: the previous cycle's manifest is written to this service's
own data root (`data_root_paths["vinu_reflection"]`, the same directory
`reflection.db` lives in) as `freeze_manifest_state.json` -- not through
`reflection_beliefs` (routine cycles write nothing there at all, per
`write_finding()`'s own contract, so it can't be trusted to hold the
prior manifest across a quiet stretch)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from vinu_infra.freeze import contamination_check, freeze_manifest
from vinu_infra.reflection import Finding, POLARITY_HIGHER_IS_WORSE

ANALYST_NAME = "governance_freshness"
CLUSTER = "Governance & Freshness"
METRIC_NAME = "manifest_drift_count"
SCOPE_KEY = "freeze_manifest"

STATE_FILENAME = "freeze_manifest_state.json"


def _state_path(data_root_paths: dict[str, Path]) -> Path:
    return Path(data_root_paths["vinu_reflection"]) / STATE_FILENAME


def _load_prior(state_path: Path) -> Optional[dict[str, Any]]:
    if not state_path.exists():
        return None
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    state_path = _state_path(data_root_paths)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    prior = _load_prior(state_path)
    current = freeze_manifest()
    state_path.write_text(json.dumps(current), encoding="utf-8")

    if prior is None:
        # First-ever cycle -- nothing to diff against yet, this cycle only
        # establishes the baseline.
        return []

    diff = contamination_check(prior, current)
    if not diff["drift"]:
        return []

    changed_count = (
        len(diff["added"]) + len(diff["removed"]) + len(diff["changed"]) + len(diff["env_changed"])
    )

    return [
        Finding(
            analyst_name=ANALYST_NAME,
            cluster=CLUSTER,
            scope_type="system",
            scope_key=SCOPE_KEY,
            signal_json={
                "added": diff["added"],
                "removed": diff["removed"],
                "changed": diff["changed"],
                "env_changed": diff["env_changed"],
            },
            evidence_count=changed_count,
            primary_metric=float(changed_count),
            metric_name=METRIC_NAME,
            psi=0.0,
            domain_floor_breached=True,
            narrative=(
                f"freeze manifest drift: {len(diff['added'])} added, "
                f"{len(diff['removed'])} removed, {len(diff['changed'])} changed, "
                f"{len(diff['env_changed'])} env var(s) changed since the prior cycle"
            ),
        )
    ]


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="prior_cycle_manifest_vs_current_cycle_manifest",
        reason=(
            "H (consistency): any unexplained drift in data-root file hashes "
            "or VINU_* env vars between cycles is worth a look -- more changed "
            "items is worse, domain-floor-triggered rather than PSI-trended"
        ),
        updated_by=ANALYST_NAME,
    )
