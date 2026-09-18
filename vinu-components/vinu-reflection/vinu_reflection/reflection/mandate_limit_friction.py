"""Analysis O -- are operator mandate limits protecting against real risk,
or just friction. Design reference: missing-pieces-of-system/
maturity-agentic-system/thinking-1/02-decided-pattern/25-A-Y-details/
05-governance-freshness.md ("O").

Was blocked until 2026-09-20: `order_rejected` audit entries carried no
`artifact_id` at all, so "which artifact did an operator-limit rejection
block" needed a weak symbol+time-window match. The new writer that
closes that gap is `OrderGuard.check()`'s four operator-limit rejection
sites (`vinu-agent/vinu_agent/broker/order_guard.py`) now populating
`GuardResult.blocked_artifact_ids`, surfaced into `order_rejected` audit
entries by `trade_tool.py`. This module is the read+join side.

"Eventual projected performance... where trackable" (this analysis's own
Source stores note) is read from `decay_snapshots` via
`SqliteStrategyStore.get_latest_snapshot(artifact_id)` -- a snapshot's
mere existence for a blocked artifact already means it's still being
tracked (BENCHING/MONITORING/ACTIVE all get decay snapshots computed);
an artifact with no snapshot at all isn't trackable and is skipped, not
counted as a bad outcome. `evaluation == "HEALTHY"` (the real, only
"nothing wrong" value `vinu_research/decay.py`'s `evaluate_health`/
`evaluate_strategy_health` ever return) is the "good outcome" flag --
matches this analysis's own Condition ("show typical or above-typical
projected performance").
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_LOWER_IS_WORSE,
    population_stability_index,
)

from vinu_agent.broker.kill_switch import AuditLogger
from vinu_agent.broker.research_link import get_strategy_store

ANALYST_NAME = "mandate_limit_friction"
CLUSTER = "Governance & Freshness"
METRIC_NAME = "healthy_fraction_delta"

# Rejections behind an operator-set mandate limit are inherently rarer
# than raw order flow (this analysis's own Manageability note: "typically
# small in practice, not the full watchlist") -- a lower floor than D/C's
# 30 is the right order of magnitude for a per-symbol comparison this
# thin, same reasoning U/Y/K used for their own evidence floors.
MIN_EVIDENCE_COUNT = 10

_HEALTHY_EVALUATION = "HEALTHY"


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_agent"]` must point at a mounted copy of
    vinu-agent's own data root (same mount `decision_process.py` etc.
    already use). The strategy store comes from `get_strategy_store()`
    (reads `VINU_RESEARCH_DATA_ROOT` directly), same as B/V
    (`regime_strategy_coverage.py`/`paper_live_correlation.py`) --
    `data_root_paths` has no `"vinu_research"` key at all in the real
    wiring (`cli.py`'s `reflection_worker_main`), only vinu_agent/
    vinu_live/vinu_screener/vinu_portfolio/vinu_stock/vinu_reflection."""
    agent_root = Path(data_root_paths["vinu_agent"])
    strategy_store = get_strategy_store()

    rejections = AuditLogger.read_all(
        action="order_rejected", log_path=agent_root / "trade_audit.log",
    )

    # (symbol -> list[bool healthy]), plus one system-wide pool across
    # every symbol -- the reference distribution each symbol's own is
    # compared against.
    by_symbol: dict[str, list[bool]] = defaultdict(list)
    system_wide: list[bool] = []
    seen_artifact_ids: set[str] = set()

    for entry in rejections:
        symbol = entry.get("symbol", "")
        details = entry.get("details") or {}
        artifact_ids = details.get("blocked_artifact_ids") or []
        for artifact_id in artifact_ids:
            # A tighter limit can reject the same still-open position
            # repeatedly across cycles -- count each artifact's eventual
            # outcome once, not once per rejection it was ever party to.
            if artifact_id in seen_artifact_ids:
                continue
            seen_artifact_ids.add(artifact_id)
            snapshot = strategy_store.get_latest_snapshot(artifact_id)
            if snapshot is None:
                continue  # not trackable -- never entered BENCHING/MONITORING
            healthy = snapshot.evaluation == _HEALTHY_EVALUATION
            if symbol:
                by_symbol[symbol].append(healthy)
            system_wide.append(healthy)

    findings: list[Finding] = []
    if len(system_wide) < MIN_EVIDENCE_COUNT:
        return findings

    for symbol, labels in by_symbol.items():
        if len(labels) < MIN_EVIDENCE_COUNT:
            continue
        symbol_healthy_fraction = sum(labels) / len(labels)
        system_healthy_fraction = sum(system_wide) / len(system_wide)
        delta = symbol_healthy_fraction - system_healthy_fraction

        # Reference = the system-wide baseline every symbol is judged
        # against, current = this symbol's own distribution -- same
        # two-group PSI shape as D/K, recomputed fresh every cycle.
        psi = population_stability_index(
            [float(v) for v in system_wide], [float(v) for v in labels],
            bin_count=2, min_samples_per_bin=1,
        )

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="ticker",
                scope_key=symbol,
                signal_json={
                    "blocked_count": len(labels),
                    "projected_performance_of_blocked": symbol_healthy_fraction,
                    "system_healthy_fraction": system_healthy_fraction,
                },
                evidence_count=len(labels),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{symbol}: {symbol_healthy_fraction:.2f} of {len(labels)} blocked "
                    f"artifacts still trackable are HEALTHY, vs {system_healthy_fraction:.2f} system-wide"
                ),
            )
        )
    return findings


def seed_reference_config(reflection_store) -> None:
    """Idempotent, same "seed on every worker-cycle start" posture as
    every other analyst here."""
    reflection_store.upsert_reference_config(
        analyst_name=ANALYST_NAME,
        scope_type="ticker",
        metric_name=METRIC_NAME,
        metric_polarity=POLARITY_LOWER_IS_WORSE,
        reference_window_definition="system_wide_trackable_blocked_artifacts",
        reason="O: a symbol whose blocked artifacts stay healthier than the "
        "system baseline suggests its mandate limit is blocking otherwise-fine trades",
        updated_by=ANALYST_NAME,
    )
