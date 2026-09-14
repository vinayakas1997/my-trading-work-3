"""Self-calibrating TradeScore weights (high-expectations follow-up).

TradeScoreThresholds (config.py) has always been meant to be calibrated --
its own docstring says "override only in tests or a future calibration
pass" -- but every trade plan has always been scored against the same
hand-picked defaults. Fitting those weights once against a handful of
trades would be fitting noise, not signal. This module is the same
*adaptive* machinery decay.py already uses for strategy health: it stays
inert (below the sample-size floor, "insufficient_sample", no change)
until there is enough real data, then nudges weights in small, bounded
steps toward whatever historically predicted winning trades -- never a
full refit, never unbounded drift.

record_trade_score_outcome's rows come from record_realized_outcome
(trade_plan_authoring.py), which already loads the frozen TradePlan --
including its trade_score's 4 sub-scores -- at the moment a closed
position's actual_return_pct is known. No new data flow from vinu-live.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import statistics
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from vinu_research.config import TradeScoreThresholds

logger = logging.getLogger(__name__)

_SCORE_FIELDS = ("confluence_score", "ev_score", "risk_score", "regime_fit_score")
# TradeScoreResult's sub-score field names (what history rows are keyed by)
# vs. TradeScoreThresholds' corresponding max-points field names -- these
# are deliberately different names on the two dataclasses (a score vs. a
# ceiling), so propose_calibrated_thresholds needs this mapping to move
# between them.
_SCORE_TO_MAX_FIELD = {
    "confluence_score": "confluence_max",
    "ev_score": "ev_max",
    "risk_score": "risk_max",
    "regime_fit_score": "regime_fit_max",
}

DEFAULT_HISTORY_PATH = os.environ.get(
    "VINU_TRADE_SCORE_CALIBRATION_HISTORY",
    os.environ.get("VINU_RESEARCH_DATA_ROOT", str(Path.home() / ".vinu-research"))
    + "/trade_score_calibration_history.jsonl",
)
DEFAULT_STATE_PATH = os.environ.get(
    "VINU_TRADE_SCORE_CALIBRATION_STATE",
    os.environ.get("VINU_RESEARCH_DATA_ROOT", str(Path.home() / ".vinu-research"))
    + "/trade_score_calibration.json",
)


# ---------------------------------------------------------------------------
# History: one row per closed trade, joining its trade_score sub-scores to
# its realized outcome.
# ---------------------------------------------------------------------------


def record_trade_score_outcome(
    trade_score: Any, direction: str, actual_return_pct: float, *, log_path: str | Path | None = None,
) -> None:
    """Best-effort append (never raises -- same contract as every other
    audit/log writer in this codebase). `trade_score` is a TradeScoreResult
    (or None, in which case this is a silent no-op -- an old plan predating
    Phase 3's gate has nothing to record)."""
    if trade_score is None:
        return
    try:
        path = Path(log_path) if log_path is not None else Path(DEFAULT_HISTORY_PATH)
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "timestamp": time.time(),
            "direction": direction,
            "actual_return_pct": actual_return_pct,
            "tier": getattr(trade_score, "tier", ""),
            "total_score": getattr(trade_score, "total_score", 0.0),
        }
        for field in _SCORE_FIELDS:
            row[field] = getattr(trade_score, field, 0.0)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, default=str) + "\n")
    except Exception:  # noqa: BLE001 -- best-effort, see module docstring
        logger.exception("Failed to record trade_score outcome, continuing without it")


def read_history(*, log_path: str | Path | None = None) -> list[dict[str, Any]]:
    path = Path(log_path) if log_path is not None else Path(DEFAULT_HISTORY_PATH)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


# ---------------------------------------------------------------------------
# Metrics: does each sub-score actually predict realized return?
# ---------------------------------------------------------------------------


def compute_calibration_metrics(history: list[dict[str, Any]], min_sample: int = 30) -> dict[str, Any]:
    """{"status": "insufficient_sample"} below `min_sample` -- same status
    convention pnl_attribution's _rate_with_ci already uses. Else a Pearson
    correlation (stdlib statistics.correlation, same module decay.py's own
    metrics already use) between each of the 4 sub-scores and
    actual_return_pct across the whole history."""
    n = len(history)
    if n < min_sample:
        return {"status": "insufficient_sample", "n_entries": n, "min_sample": min_sample}

    returns = [float(h.get("actual_return_pct", 0.0)) for h in history]
    correlations: dict[str, float] = {}
    for field in _SCORE_FIELDS:
        values = [float(h.get(field, 0.0)) for h in history]
        # statistics.correlation raises StatisticsError on zero-variance
        # input (every trade scored identically on this component) -- 0.0
        # correlation is the correct reading (no relationship observable),
        # not a failure.
        try:
            correlations[field] = statistics.correlation(values, returns)
        except statistics.StatisticsError:
            correlations[field] = 0.0

    return {"status": "ok", "n_entries": n, "correlations": correlations}


def propose_calibrated_thresholds(
    current: TradeScoreThresholds, metrics: dict[str, Any], bound: float = 0.2,
) -> TradeScoreThresholds | None:
    """None when there's no actionable signal (insufficient sample, or
    every component's correlation with realized return is non-positive --
    a negative correlation means MORE weight there would be actively wrong,
    so this declines to act rather than inverting anything). Otherwise a
    new TradeScoreThresholds with the 4 sub-maxes reallocated proportional
    to relative (non-negative) correlation strength, each individual max's
    change clamped to +-bound of its current value -- tier cutoffs
    (strong/moderate/watch_threshold) are untouched, intentionally out of
    scope for this iteration. The 4 clamped maxes are NOT forced to sum
    back to the current total ceiling: the target allocation (before
    clamping) always sums to it exactly, but rescaling AFTER clamping to
    restore that sum would reopen the very bound this function exists to
    enforce -- a component with a strong signal could be pushed back past
    +-bound to make the total add up. The bound is the safety property
    that matters here; a small drift in the total ceiling (at most the sum
    of however far clamping pulled each component from its target) is an
    accepted, minor side effect, not compensated for."""
    if metrics.get("status") != "ok":
        return None
    correlations = metrics.get("correlations", {})
    positive = {f: max(0.0, correlations.get(f, 0.0)) for f in _SCORE_FIELDS}
    total_positive = sum(positive.values())
    if total_positive <= 0:
        return None

    current_maxes = {f: getattr(current, _SCORE_TO_MAX_FIELD[f]) for f in _SCORE_FIELDS}
    total_ceiling = sum(current_maxes.values())

    target = {f: total_ceiling * (positive[f] / total_positive) for f in _SCORE_FIELDS}
    clamped = {
        f: min(max(target[f], current_maxes[f] * (1 - bound)), current_maxes[f] * (1 + bound))
        for f in _SCORE_FIELDS
    }

    # dataclasses.replace copies every other field (tier cutoffs, cost
    # heuristics, min_tradeable_tier, min_reward_risk_ratio, ...) from
    # `current` unchanged -- only the 4 sub-maxes are touched here, so this
    # can never silently drop a field the dataclass gains in the future.
    return dataclasses.replace(
        current,
        **{_SCORE_TO_MAX_FIELD[f]: clamped[f] for f in _SCORE_FIELDS},
    )


# ---------------------------------------------------------------------------
# State: the currently-active thresholds, plus a pending propose-mode
# proposal awaiting human approval.
# ---------------------------------------------------------------------------

_FIELD_NAMES = tuple(TradeScoreThresholds.__dataclass_fields__.keys())


def _thresholds_to_dict(t: TradeScoreThresholds) -> dict[str, Any]:
    return {name: getattr(t, name) for name in _FIELD_NAMES}


def _thresholds_from_dict(d: dict[str, Any]) -> TradeScoreThresholds:
    return TradeScoreThresholds(**{k: v for k, v in d.items() if k in _FIELD_NAMES})


def _read_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def load_active_thresholds(*, state_path: str | Path | None = None) -> TradeScoreThresholds:
    """The currently-active calibrated thresholds, or the plain defaults
    when no calibration has ever been approved/applied -- fail-open on any
    missing/corrupt state file, same posture as every other optional data
    source in this codebase."""
    path = Path(state_path) if state_path is not None else Path(DEFAULT_STATE_PATH)
    state = _read_state(path)
    active = state.get("active")
    if not active:
        return TradeScoreThresholds()
    try:
        return _thresholds_from_dict(active)
    except Exception:
        logger.warning("Corrupt active trade_score calibration state, falling back to defaults")
        return TradeScoreThresholds()


def save_proposal(
    thresholds: TradeScoreThresholds, metrics: dict[str, Any], *, state_path: str | Path | None = None,
) -> None:
    path = Path(state_path) if state_path is not None else Path(DEFAULT_STATE_PATH)
    state = _read_state(path)
    state["proposal"] = {
        "thresholds": _thresholds_to_dict(thresholds),
        "metrics": metrics,
        "proposed_at": datetime.now(timezone.utc).isoformat(),
    }
    _write_state(path, state)


def get_pending_proposal(*, state_path: str | Path | None = None) -> dict[str, Any] | None:
    path = Path(state_path) if state_path is not None else Path(DEFAULT_STATE_PATH)
    return _read_state(path).get("proposal")


def approve_proposal(
    approver: str, *, state_path: str | Path | None = None,
) -> TradeScoreThresholds:
    """Human confirms a propose-mode calibration recorded by
    ScheduledResearchExecutor.trade_score_calibration_scan(). Mirrors
    decay.approve_decay_action's contract exactly -- `approver` is a
    required parameter with no default, human accountability, not a silent
    bypass."""
    if not approver:
        raise ValueError("approver is required")
    path = Path(state_path) if state_path is not None else Path(DEFAULT_STATE_PATH)
    state = _read_state(path)
    proposal = state.get("proposal")
    if not proposal:
        raise ValueError("no pending trade_score calibration proposal")
    thresholds = _thresholds_from_dict(proposal["thresholds"])
    state["active"] = proposal["thresholds"]
    state["active_metadata"] = {
        "approved_by": approver,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "metrics": proposal.get("metrics"),
    }
    state.pop("proposal", None)
    _write_state(path, state)
    return thresholds


def apply_directly(
    thresholds: TradeScoreThresholds, metrics: dict[str, Any], *, state_path: str | Path | None = None,
) -> None:
    """Auto mode only -- applies a new calibration without human approval."""
    path = Path(state_path) if state_path is not None else Path(DEFAULT_STATE_PATH)
    state = _read_state(path)
    state["active"] = _thresholds_to_dict(thresholds)
    state["active_metadata"] = {
        "applied_at": datetime.now(timezone.utc).isoformat(),
        "mode": "auto",
        "metrics": metrics,
    }
    state.pop("proposal", None)
    _write_state(path, state)
