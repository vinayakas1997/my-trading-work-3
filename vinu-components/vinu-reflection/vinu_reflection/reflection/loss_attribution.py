"""Analysis C -- loss-cause / slippage attribution. Per trade_score_tier,
checks whether the loss rate among recently closed trades has drifted
from that tier's own prior trailing window. Design reference:
missing-pieces-of-system/maturity-agentic-system/thinking-1/02-decided-pattern/
25-A-Y-details/03-execution-money-flow.md ("C").

**Scoping correction found while implementing**: the design doc's
`(trade_score_tier, risk_band)` cross-tab assumes `risk_band` is a
categorical label. The real field (`RiskBand`, vinu-research/vinu_research/
models.py:257-276) is a bag of numeric limits (`max_position_size_pct`,
`max_leverage`, ...) with no categorical label anywhere in the codebase
-- bucketing it into bands would mean inventing a new, untested
classification scheme, not reading one that already exists. Scoped down
to `trade_score_tier` alone (a real, small, fixed set --
`"no_trade"|"watch"|"moderate"|"strong"`, vinu-research/vinu_research/
gates/trade_score_gate.py:27), same "reuse what's real, flag what isn't"
posture as D/L/M/A's own scope-downs.

Windowing follows angle_trust.py's precedent (two adjacent,
non-overlapping windows compared via the shared PSI machinery) rather
than a bespoke percentile-band function, for the same reasons given
there.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from vinu_infra.reflection import (
    Finding,
    POLARITY_HIGHER_IS_WORSE,
    population_stability_index,
)
from vinu_infra.trade_audit_log import read_all

ANALYST_NAME = "execution_money_flow"
CLUSTER = "Execution & Money-Flow"
METRIC_NAME = "loss_rate"

CURRENT_WINDOW = 30
REFERENCE_WINDOW_MAX = 90
MIN_REFERENCE_WINDOW = 30


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)


def run(
    data_root_paths: dict[str, Path],
    service_clients: Optional[dict[str, Any]] = None,
) -> list[Finding]:
    """`data_root_paths["vinu_live"]` must point at a mounted copy of
    vinu-live's own data root (docker-compose.yml mounts `./data/live`
    read-only into this service at `/live-data`) -- the directory
    containing `trade_audit_log.jsonl`, not the file itself."""
    log_path = Path(data_root_paths["vinu_live"]) / "trade_audit_log.jsonl"
    rows = read_all(log_path=log_path)

    entry_tier: dict[str, str] = {}
    entry_slippage: dict[str, Optional[float]] = {}
    # tier -> closed trades, in the chronological (file) order they exited.
    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for row in rows:
        trade_id = row.get("trade_id")
        if not trade_id:
            continue
        event = row.get("event")
        if event == "entry":
            entry_tier[trade_id] = row.get("trade_score_tier", "")
            entry_slippage[trade_id] = row.get("slippage_bps")
        elif event == "exit":
            tier = entry_tier.get(trade_id)
            realized_pnl = row.get("realized_pnl")
            if tier is None or realized_pnl is None:
                continue
            by_tier[tier].append(
                {
                    "realized_pnl": realized_pnl,
                    "loss_cause": row.get("loss_cause", ""),
                    "slippage_bps": entry_slippage.get(trade_id),
                }
            )

    findings: list[Finding] = []
    for tier, trades in by_tier.items():
        if len(trades) < CURRENT_WINDOW + MIN_REFERENCE_WINDOW:
            continue

        window = trades[-(CURRENT_WINDOW + REFERENCE_WINDOW_MAX):]
        current = window[-CURRENT_WINDOW:]
        reference = window[:-CURRENT_WINDOW]
        if len(reference) < MIN_REFERENCE_WINDOW:
            continue

        current_losses = [1.0 if t["realized_pnl"] < 0 else 0.0 for t in current]
        reference_losses = [1.0 if t["realized_pnl"] < 0 else 0.0 for t in reference]
        current_loss_rate = _mean(current_losses)
        reference_loss_rate = _mean(reference_losses)
        delta = current_loss_rate - reference_loss_rate

        psi = population_stability_index(
            reference_losses, current_losses, bin_count=2, min_samples_per_bin=1
        )

        slippages = [
            t["slippage_bps"] for t in current if isinstance(t.get("slippage_bps"), (int, float))
        ]
        mean_slippage_bps = _mean(slippages) if slippages else 0.0

        cause_counts: dict[str, int] = {}
        for t in current:
            if t["realized_pnl"] < 0:
                cause = t.get("loss_cause") or "unclassified"
                cause_counts[cause] = cause_counts.get(cause, 0) + 1
        dominant_loss_cause = max(cause_counts, key=cause_counts.get) if cause_counts else ""

        findings.append(
            Finding(
                analyst_name=ANALYST_NAME,
                cluster=CLUSTER,
                scope_type="system",
                scope_key=tier,
                signal_json={
                    "loss_rate": current_loss_rate,
                    "reference_loss_rate": reference_loss_rate,
                    "mean_slippage_bps": mean_slippage_bps,
                    "dominant_loss_cause": dominant_loss_cause,
                },
                evidence_count=len(window),
                primary_metric=delta,
                metric_name=METRIC_NAME,
                psi=psi,
                narrative=(
                    f"{tier}: loss rate {current_loss_rate:.2f} (latest {CURRENT_WINDOW}) "
                    f"vs. {reference_loss_rate:.2f} (prior {len(reference)})"
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
        reference_window_definition="trailing_90_closed_trades_before_the_latest_30",
        reason="C: a higher loss rate for a decision-context tier is worse",
        updated_by=ANALYST_NAME,
    )
