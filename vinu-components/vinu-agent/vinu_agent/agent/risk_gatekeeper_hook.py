"""Turns risk_gatekeeper's APPROVED verdict into a real status transition:
the reviewed artifact moves BENCHING/MONITORING -> PEND via
SqliteStrategyStore.mark_pend() (Phase 2, New-talk-agents/new-thinking/
new-restructure/phases/phase-2-funding-mechanics/) -- funding itself is
capital_allocator's decision now, made across a batch on its own cadence,
not risk_gatekeeper's alone. REJECTED writes no status change -- the
artifact stays exactly where it was -- but DOES write a TickerLedger
"REJECTED" row (Phase 7, .../phase-7-significance-triage/, added when
that phase's pattern detection needed real REJECTED history to query and
found none was ever recorded). Never an agent tool (pillar 8) -- called
from TeamManager.run() after the manager's final answer is parsed, same
shape as research_artifact_writer.py.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

LOG = logging.getLogger(__name__)

_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_json_block(content: str) -> Optional[dict]:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def apply_risk_gatekeeper_verdict(
    content: str, *, strategy_store: Any, ticker_ledger_store: Any = None
) -> Optional[str]:
    """Best-effort: any failure here is logged and swallowed, never raised
    (same contract as broker/debrief.py) -- a storage hiccup shouldn't take
    down the whole team run after the manager already produced its answer.
    Returns the artifact_id on a real PEND transition, else None.

    `ticker_ledger_store` (Phase 0) is optional and its own write is
    best-effort/never blocking -- the real PEND transition happens first
    and stands regardless of whether the audit row succeeds, same
    "audit-write-never-blocks-a-real-action" ordering principle used
    throughout the later phases.
    """
    try:
        data = _extract_json_block(content)
        if not data:
            return None
        verdict = data.get("verdict")
        artifact_id = str(data.get("artifact_id", "")).strip()
        if not artifact_id or verdict not in ("APPROVED", "REJECTED"):
            return None
    except Exception:
        LOG.exception("failed to parse risk_gatekeeper verdict, continuing without it")
        return None

    if verdict == "REJECTED":
        if ticker_ledger_store is not None:
            try:
                artifact = strategy_store.get_artifact(artifact_id)
                ticker = artifact.universe[0] if artifact and artifact.universe else ""
                if ticker:
                    ticker_ledger_store.add_event(
                        ticker=ticker, stage="risk_gatekeeper", event_type="REJECTED",
                        text=str(data.get("reason", "")), ref_id=artifact_id, source="watchlist",
                    )
            except Exception:
                LOG.exception("failed to write TickerLedger row for %s REJECTED verdict, continuing without it", artifact_id)
        return None

    try:
        approved_size = float(data.get("approved_size", 0.0) or 0.0)
    except (TypeError, ValueError):
        approved_size = 0.0

    # Implementation-plan task 05 (shortcoming #7): risk_gatekeeper's
    # approved_size now comes from a real formula, not an LLM-picked number.
    # The manager records the sizing_inputs the compute_position_size tool
    # used (win_rate, payoff_ratio, account_equity, method, ...); when they
    # are present the hook recomputes the formula deterministically and
    # stores min(formula size, the concentration-headroom cap the manager
    # reported) -- the formula is authoritative, the headroom caps it. When
    # no sizing_inputs are recorded (pre-task-05 verdicts), the manager's
    # number passes through unchanged, preserving existing behavior.
    formula_size: float | None = None
    sizing_inputs = data.get("sizing_inputs")
    if isinstance(sizing_inputs, dict) and sizing_inputs:
        try:
            from .position_sizing import compute_position_size

            result = compute_position_size(
                account_equity=float(sizing_inputs.get("account_equity", 0.0) or 0.0),
                method=str(sizing_inputs.get("method", "fractional_kelly")),
                win_rate=float(sizing_inputs.get("win_rate", 0.0) or 0.0),
                payoff_ratio=float(sizing_inputs.get("payoff_ratio", 0.0) or 0.0),
                kelly_fraction=float(sizing_inputs.get("kelly_fraction", 0.25) or 0.25),
                risk_pct=float(sizing_inputs.get("risk_pct", 0.02) or 0.02),
                entry_price=float(sizing_inputs.get("entry_price", 0.0) or 0.0),
                atr=float(sizing_inputs.get("atr", 0.0) or 0.0),
                atr_stop_multiple=float(sizing_inputs.get("atr_stop_multiple", 2.0) or 2.0),
            )
            if result.get("status") == "ok":
                formula_size = float(result.get("size", 0.0) or 0.0)
        except Exception:
            LOG.exception("failed to recompute formula size from sizing_inputs, using manager approved_size")
            formula_size = None
    if formula_size is not None:
        approved_size = min(approved_size, formula_size) if approved_size > 0 else formula_size

    try:
        artifact = strategy_store.mark_pend(artifact_id, approved_size=approved_size)
    except Exception:
        LOG.exception(
            "failed to mark %s PEND after risk_gatekeeper APPROVED, continuing without it",
            artifact_id,
        )
        return None

    if ticker_ledger_store is not None:
        try:
            ticker = artifact.universe[0] if artifact.universe else ""
            if ticker:
                ticker_ledger_store.add_event(
                    ticker=ticker,
                    stage="risk_gatekeeper",
                    event_type="PEND",
                    text=(
                        f"risk_gatekeeper APPROVED, moved to PEND, approved_size={approved_size}"
                        + (f", sizing_inputs={json.dumps(sizing_inputs)}" if sizing_inputs else "")
                    ),
                    ref_id=artifact_id,
                    source="watchlist",
                )
        except Exception:
            LOG.exception("failed to write TickerLedger row for %s PEND transition, continuing without it", artifact_id)

    return artifact_id
