from __future__ import annotations

import statistics
from typing import Any

from vinu_research.config import DecayThresholds
from vinu_research.models import ArtifactStatus, BenchEntry, DecaySnapshot


def compute_decay_metrics(
    bench_history: list[BenchEntry],
) -> dict[str, float]:
    if len(bench_history) < 2:
        return {
            "ic_ratio": 0.0,
            "rolling_ir": 0.0,
            "ic_positive_ratio": 0.0,
            "rolling_sharpe": 0.0,
            "n_entries": len(bench_history),
        }

    baseline = bench_history[:5] if len(bench_history) >= 5 else bench_history[:]
    rolling = bench_history

    baseline_ic = statistics.mean(e.ic for e in baseline) if baseline else 0.0
    rolling_ic = statistics.mean(e.ic for e in rolling) if rolling else 0.0
    ic_ratio = rolling_ic / baseline_ic if abs(baseline_ic) > 1e-10 else 0.0

    ic_values = [e.ic for e in rolling]
    rolling_ir = (
        (statistics.mean(ic_values) / statistics.stdev(ic_values))
        if len(ic_values) > 1 and statistics.stdev(ic_values) > 0
        else 0.0
    )

    ic_pos_count = sum(1 for e in rolling if e.ic_positive)
    ic_positive_ratio = ic_pos_count / len(rolling) if rolling else 0.0

    rolling_sharpe = statistics.mean(e.sharpe for e in rolling) if rolling else 0.0

    return {
        "ic_ratio": ic_ratio,
        "rolling_ir": rolling_ir,
        "ic_positive_ratio": ic_positive_ratio,
        "rolling_sharpe": rolling_sharpe,
        "n_entries": len(bench_history),
    }


def evaluate_health(
    metrics: dict[str, float],
    thresholds: DecayThresholds | None = None,
) -> str:
    t = thresholds or DecayThresholds()

    ic_ratio = metrics.get("ic_ratio", 0.0)
    rolling_ir = metrics.get("rolling_ir", 0.0)
    ic_pos = metrics.get("ic_positive_ratio", 0.0)
    rolling_sharpe = metrics.get("rolling_sharpe", 0.0)

    def _score(value: float, healthy: float, warning: float, critical: float) -> int:
        if value >= healthy:
            return 1
        if value >= warning:
            return 0
        if value >= critical:
            return -1
        return -2

    scores = 0
    scores += _score(ic_ratio, t.ic_ratio_healthy, t.ic_ratio_warning, t.ic_ratio_critical)
    scores += _score(rolling_ir, t.ir_healthy, t.ir_warning, t.ir_critical)
    scores += _score(ic_pos, t.ic_pos_healthy, t.ic_pos_warning, t.ic_pos_critical)
    scores += _score(rolling_sharpe, t.sharpe_healthy, t.sharpe_warning, t.sharpe_critical)

    if scores >= 3:
        return "HEALTHY"
    elif scores >= 0:
        return "WARNING"
    elif scores >= -5:
        return "DECAYED"
    else:
        return "CRITICAL"


def compute_decay_snapshot(
    artifact_id: str,
    bench_history: list[BenchEntry],
    thresholds: DecayThresholds | None = None,
) -> DecaySnapshot:
    metrics = compute_decay_metrics(bench_history)
    evaluation = evaluate_health(metrics, thresholds)
    from datetime import datetime, timezone
    return DecaySnapshot(
        artifact_id=artifact_id,
        evaluation=evaluation,
        ic_ratio=metrics["ic_ratio"],
        rolling_ir=metrics["rolling_ir"],
        ic_positive_ratio=metrics["ic_positive_ratio"],
        rolling_sharpe=metrics["rolling_sharpe"],
        n_entries=metrics["n_entries"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def compute_strategy_decay_metrics(
    bench_history: list[BenchEntry],
) -> dict[str, float]:
    """Sharpe-only decay signal for single-strategy artifacts (as opposed to
    factor artifacts, whose bench entries carry real ic/ir). A strategy's
    bench_history is a series of re-backtest Sharpe ratios over time; decay is
    "current Sharpe vs. the Sharpe it was approved with," not a cross-sectional
    IC/IR — those fields don't apply here and are always 0.0 on this artifact
    type, so evaluate_health()'s ic/ir/ic_positive scoring would always read
    CRITICAL and disable every approved strategy within a handful of scans."""
    if len(bench_history) < 2:
        return {"sharpe_ratio": 0.0, "rolling_sharpe": 0.0, "n_entries": len(bench_history)}

    baseline = bench_history[:5] if len(bench_history) >= 5 else bench_history[:]
    baseline_sharpe = statistics.mean(e.sharpe for e in baseline) if baseline else 0.0
    rolling_sharpe = statistics.mean(e.sharpe for e in bench_history)
    sharpe_ratio = (
        rolling_sharpe / baseline_sharpe if abs(baseline_sharpe) > 1e-10 else 0.0
    )
    return {
        "sharpe_ratio": sharpe_ratio,
        "rolling_sharpe": rolling_sharpe,
        "n_entries": len(bench_history),
    }


def evaluate_strategy_health(
    metrics: dict[str, float],
    thresholds: DecayThresholds | None = None,
) -> str:
    """Health verdict from rolling-Sharpe-vs-baseline-Sharpe ratio alone,
    reusing DecayThresholds.ic_ratio_* bands (same "ratio of current to
    baseline" semantics, just applied to Sharpe instead of IC)."""
    t = thresholds or DecayThresholds()
    ratio = metrics.get("sharpe_ratio", 0.0)
    if metrics.get("n_entries", 0) < 2:
        return "HEALTHY"
    if ratio >= t.ic_ratio_healthy:
        return "HEALTHY"
    if ratio >= t.ic_ratio_warning:
        return "WARNING"
    if ratio >= t.ic_ratio_critical:
        return "DECAYED"
    return "CRITICAL"


def compute_strategy_decay_snapshot(
    artifact_id: str,
    bench_history: list[BenchEntry],
    thresholds: DecayThresholds | None = None,
) -> DecaySnapshot:
    metrics = compute_strategy_decay_metrics(bench_history)
    evaluation = evaluate_strategy_health(metrics, thresholds)
    from datetime import datetime, timezone
    return DecaySnapshot(
        artifact_id=artifact_id,
        evaluation=evaluation,
        ic_ratio=metrics["sharpe_ratio"],
        rolling_sharpe=metrics["rolling_sharpe"],
        n_entries=metrics["n_entries"],
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


def transition_status(
    current: ArtifactStatus,
    evaluation_history: list[str],
    live_sharpe: float | None = None,
    backtest_sharpe: float | None = None,
) -> ArtifactStatus:
    if not evaluation_history:
        return current

    last = evaluation_history[-1]

    if current == ArtifactStatus.BENCHING:
        if live_sharpe is not None and backtest_sharpe is not None and backtest_sharpe != 0:
            degradation = (backtest_sharpe - live_sharpe) / abs(backtest_sharpe)
            if live_sharpe > 0 and degradation <= 0.5:
                return ArtifactStatus.ACTIVE

    elif current == ArtifactStatus.ACTIVE:
        if _n_consecutive(evaluation_history, {"WARNING", "DECAYED", "CRITICAL"}, 3):
            return ArtifactStatus.MONITORING

    elif current == ArtifactStatus.MONITORING:
        if last == "HEALTHY":
            return ArtifactStatus.ACTIVE
        if _n_consecutive(evaluation_history, {"DECAYED", "CRITICAL"}, 2):
            return ArtifactStatus.DECAYED

    elif current == ArtifactStatus.DECAYED:
        if _n_consecutive(evaluation_history, {"CRITICAL"}, 3):
            return ArtifactStatus.DISABLED

    return current


def _n_consecutive(
    history: list[str],
    targets: set[str],
    n: int,
) -> bool:
    if len(history) < n:
        return False
    return all(e in targets for e in history[-n:])
