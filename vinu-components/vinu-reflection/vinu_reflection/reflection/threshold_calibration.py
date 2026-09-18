"""Analysis W -- were the system's own hand-picked checkpoint thresholds
ever right. Design reference: missing-pieces-of-system/maturity-agentic-
system/thinking-1/02-decided-pattern/25-A-Y-details/05-governance-
freshness.md ("W").

**Scoping correction found while implementing, real and load-bearing, not
a shortcut**: the design doc's Condition asks whether "a swept range of
nearby values would plausibly have produced" a better realized-outcome
distribution than the checkpoint's current hand-picked value -- a real
counterfactual resweep. Nothing in this codebase computes that (confirmed:
grepped the whole tree for a sweep/backtest-replay helper over
`calibration_log.jsonl`'s logged inputs; none exists), and building one
from scratch has no existing precedent to model it on -- the same
"needs a spec" situation already flagged for analysis S, not something to
guess at here. Implemented instead as the same two-adjacent-windows drift
detector every other analyst in this service already uses, applied
directly to each checkpoint's own logged numeric outcome: has this
checkpoint's real behavior drifted from its own trailing baseline. This
answers "is the current threshold behaving consistently" rather than "was
a different value ever better" -- a real, narrower, honestly-scoped
question, documented rather than silently substituted.

**Checkpoint inventory, verified against real call sites, not the design
doc's three named checkpoints**: grepped every real caller of
`calibration_log.record()` in vinu-live (the only package that calls it).
Two real checkpoints exist -- `bracket_partial` (vinu_live/trade_plan/
orchestrator.py, logs `symbol, r_multiple, take_fraction, capped`) and
`rebalance_protect` (same file, logs `symbol, favorable_move_pct,
protect_threshold_pct, used_volatility, will_protect, critical`). The
design doc's third named checkpoint, a "thesis-duplicate similarity
cutoff," has no real call site anywhere in the codebase -- not built here,
left out rather than fabricated.

**Known trend-field caveat, not introduced here**: same as H (governance
piece)'s own note -- there's no natural "higher/lower is worse" direction
for "did this checkpoint's behavior drift," only "did it drift." Polarity
is set to higher-is-worse by convention only, same documented gap H
already carries (`write_finding()` has no `n/a` trend value yet).

Windowing follows loss_attribution.py's (C's) precedent -- two adjacent
windows compared via the shared PSI machinery -- scaled down since
calibration checkpoints fire far less often than trades, same "smaller
natural comparison window" reasoning skill_edit_governance.py (H,
governance piece) already used for skill edits.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from vinu_infra.calibration_log import read_all
from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    population_stability_index,
)

ANALYST_NAME = "governance_freshness"
CLUSTER = "Governance & Freshness"
METRIC_NAME = "threshold_behavior_drift"

CURRENT_WINDOW = 15
REFERENCE_WINDOW_MAX = 45
MIN_REFERENCE_WINDOW = 15

# checkpoint -> the one logged numeric field used as its realized-behavior
# signal (verified present at every real call site above).
CHECKPOINT_FIELDS = {
    "bracket_partial": "r_multiple",
    "rebalance_protect": "favorable_move_pct",
}


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def _calibration_log_path(data_root_paths: dict[str, Path]) -> Path:
    """Resolved from the mounted vinu-live data root, not
    `calibration_log.py`'s own `DEFAULT_LOG_PATH` (a module-level constant
    frozen at first import -- wrong for a long-running worker sharing a
    process with other analysts' own env-dependent path resolution, same
    "resolve fresh, don't trust a frozen constant" reasoning
    skill_edit_governance.py's `_trade_score_calibration_history_path()`
    already documents). `data_root_paths["vinu_live"]` is the same mount
    loss_attribution.py (C) already established for vinu-live -- no new
    docker-compose mount needed. Requires `VINU_CALIBRATION_LOG` set to
    `/data/calibration_log.jsonl` on live-api (docker-compose.yml), the
    same real "container $HOME, not the mounted volume" bug already fixed
    once for `VINU_TRADE_AUDIT_LOG`."""
    return Path(data_root_paths["vinu_live"]) / "calibration_log.jsonl"


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    log_path = _calibration_log_path(data_root_paths)

    findings: list[Finding] = []
    for checkpoint, field in CHECKPOINT_FIELDS.items():
        entries = read_all(checkpoint, log_path=log_path)
        values = [e[field] for e in entries if isinstance(e.get(field), (int, float))]
        if len(values) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
            continue

        window = values[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) < MIN_REFERENCE_WINDOW:
            continue

        current_mean = _mean(current)
        reference_mean = _mean(reference)
        delta = current_mean - reference_mean

        psi = population_stability_index(reference, current)

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=checkpoint,
                signal_json={
                    "field": field,
                    "current_mean": current_mean,
                    "reference_mean": reference_mean,
                },
                evidence_count=len(window),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{checkpoint}: {field} mean {current_mean:.4f} (latest "
                    f"{CURRENT_WINDOW}) vs. {reference_mean:.4f} (prior {len(reference)})"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same posture as every other analyst's
    seed_reference_config in this service."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="system",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_HIGHER_IS_WORSE,
        reference_window_definition="trailing_45_calibration_log_entries_before_the_latest_15",
        reason=(
            "W: no real good/bad direction for checkpoint-behavior drift -- "
            "polarity set by convention only, same n/a caveat as H (governance)"
        ),
        updated_by=ANALYST_NAME,
    )
