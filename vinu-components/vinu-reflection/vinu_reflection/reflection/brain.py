"""Step 8 ("the brain") -- thinking-1/02-decided-pattern/00-decided-pattern.md
section 8, and its own self-trust log's exact schema,
`25-A-Y-details/07-implementation-plan-status.md`'s own "where to
continue, ranked" #2: "an LLM synthesis agent reading `reflection_beliefs`
*and* Hindsight (which doesn't exist either), producing an undesigned
'6-axis maturity profile,' plus a self-trust-tracking loop over its own
past suggestions. Deliberately not started without its own design pass
first."

**What this v1 actually builds, and what it deliberately doesn't (a real
scope, not silently smaller than advertised):**

- Reads `reflection_beliefs` (Layer 0, the "hard, always-trustworthy"
  store the design doc itself designates as the floor every other
  source is an addition on top of). Does NOT read Hindsight -- grepped
  this entire codebase and confirmed no real Hindsight client exists
  anywhere (only docstring mentions of a "future" integration), despite
  a `hindsight-llm` container running in this stack. Building against a
  client that doesn't exist would mean fabricating the integration, not
  building it.
- The "6-axis maturity profile" the design doc left undesigned: this
  build defines the 6 axes as the 6 analyst clusters themselves (the
  grouping step 3 already settled), each scored `healthy` /
  `degrading` / `insufficient_evidence` by the one LLM call, grounded
  only in the real belief rows handed to it -- never a new invented
  scalar.
- One LLM synthesis call per cycle, but ONLY when there's something to
  synthesize (at least one currently notable/significant belief) --
  most cycles still produce nothing, same "routine, nothing written"
  outcome every one of the 24 analysts already produces most of the
  time. This is what keeps the LLM cost bounded and avoids re-
  synthesizing an unchanged picture every cycle.
- Self-trust tracking is real and mechanical, not LLM-graded: a second
  LLM call judging the first would just compound uncertainty on top of
  uncertainty. Only `threshold_nudge` predictions carry a mechanically
  checkable claim (see `_resolution_criteria_for`); every other action
  type resolves `inconclusive`, honestly, rather than guessed.
- Never places an order or touches the kill switch -- `proposed_action`
  is read-only output. Wiring a real consumer to actually act on it
  (step 9: Planner / risk_gatekeeper / capital_allocator) is separate,
  deliberately scoped work, not automatic just because this file exists.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from vinu_infra.reflection import ReflectionStore

LOG = logging.getLogger(__name__)

# The 6 clusters step 3 already settled -- see cli.py's own CLUSTER
# constants across all 24 analyst modules; fixed here as the "6 axes"
# the design doc left undesigned.
CLUSTERS = (
    "Forecast Intelligence",
    "Regime & Risk Coverage",
    "Execution & Money-Flow",
    "Decision-Process / Cognition",
    "Governance & Freshness",
    "External-Signal Cross-Check",
)

_NON_ROUTINE_SEVERITIES = ("notable", "significant")

# How far out a prediction gets checked back on -- a guessed starting
# constant, same "first-pass, unvalidated" category as every other
# un-pinned threshold in this codebase (e.g. item #24's
# RECON_DRIFT_ALERT_CYCLES).
SYNTHESIS_RESOLUTION_WINDOW_DAYS = 7

_VALID_ACTION_TYPES = ("threshold_nudge", "significance_flag", "narrative_only")

# Same JSON-fenced-block convention agent/risk_gatekeeper_hook.py's own
# `_extract_json_block` already established for parsing an LLM's raw text
# response -- not a new pattern.
_JSON_BLOCK_RE = re.compile(r"```json\s*(\{.*?\})\s*```", re.DOTALL)


def gather_synthesis_inputs(store: ReflectionStore) -> list[dict[str, Any]]:
    """Every belief currently notable/significant, across all clusters.
    'Currently' means whatever `reflection_beliefs` holds right now -- a
    belief row that's gone quiet keeps its last non-routine severity
    forever, since `write_finding()` is never called again for a scope
    once it returns to routine (see that function's own docstring).
    Empty most cycles -- most days, most scopes are routine -- which is
    the correct, expected outcome, not a gap."""
    return [b for b in store.list_beliefs() if b.get("severity") in _NON_ROUTINE_SEVERITIES]


def _build_prompt(beliefs: list[dict[str, Any]]) -> str:
    rows = [
        {
            "analyst_name": b["analyst_name"],
            "cluster": b.get("cluster", ""),
            "scope_type": b["scope_type"],
            "scope_key": b["scope_key"],
            "severity": b["severity"],
            "trend": b["trend"],
            "primary_metric": b["primary_metric"],
            "narrative": b.get("narrative") or "",
            "evidence_count": b["evidence_count"],
        }
        for b in beliefs
    ]
    return (
        "You are the reflection system's step-8 synthesis agent (the "
        "\"brain\") for an automated trading system. Below are the CURRENT "
        "non-routine beliefs across all 6 analyst clusters -- each one "
        "already passed a real statistical significance gate (a PSI-based "
        "shift test), computed independently by one of 6 deterministic, "
        "non-LLM analysts. Do what no single analyst can:\n"
        "1. Notice when findings from DIFFERENT clusters are actually one "
        "story (e.g. a regime-wide move touching several unrelated-looking "
        "findings at once). Only report a connection you can point to "
        "specific listed findings for.\n"
        "2. Produce a maturity profile: exactly one status per cluster "
        "listed below, using \"insufficient_evidence\" for any cluster "
        "with no findings in the list.\n"
        "3. Optionally propose exactly one bounded action. You can never "
        "place an order or touch a kill switch -- only suggest a narrow, "
        "checkable nudge, or propose nothing at all if nothing here "
        "warrants one.\n\n"
        f"Clusters: {', '.join(CLUSTERS)}\n\n"
        f"Current non-routine beliefs (JSON):\n{json.dumps(rows, indent=2)}\n\n"
        "Respond with EXACTLY one fenced ```json block and no other text, "
        "containing an object with this exact shape:\n"
        "```json\n"
        "{\n"
        '  "connections": [{"summary": "...", "involved": [{"analyst_name": "...", '
        '"scope_type": "...", "scope_key": "..."}]}],\n'
        '  "maturity_profile": {"<cluster name>": {"status": '
        '"healthy|degrading|insufficient_evidence", "rationale": "..."}},\n'
        '  "proposed_action": {"type": "threshold_nudge|significance_flag|'
        'narrative_only|null", "description": "...", "target_analyst_name": '
        '"...", "target_scope_type": "...", "target_scope_key": "..."}\n'
        "}\n"
        "```\n"
        "`maturity_profile` must have exactly one entry per cluster listed "
        "above. Only include target_analyst_name/target_scope_type/"
        "target_scope_key when type is \"threshold_nudge\", and only "
        "referencing one of the beliefs listed above."
    )


def _extract_json_block(content: str) -> Optional[dict]:
    match = _JSON_BLOCK_RE.search(content or "")
    if not match:
        return None
    try:
        return json.loads(match.group(1))
    except json.JSONDecodeError:
        return None


def _resolution_criteria_for(action: dict[str, Any]) -> str:
    if action.get("type") == "threshold_nudge":
        return (
            f"By resolve_by, {action.get('target_analyst_name')}'s belief for "
            f"(scope_type={action.get('target_scope_type')}, "
            f"scope_key={action.get('target_scope_key')}) should not have been "
            "freshly re-confirmed as 'significant' severity since this synthesis."
        )
    return (
        "This action type has no mechanically-checkable criterion -- resolved "
        "as 'inconclusive' by the periodic resolver rather than guessed."
    )


def run_synthesis(
    store: ReflectionStore, llm: Any, *, trigger_reason: str = "scheduled",
) -> Optional[str]:
    """The brain's one LLM call for this cycle. Returns the new
    `synthesis_id`, or None when there's nothing to synthesize (no
    non-routine beliefs right now) or the LLM's response couldn't be
    parsed into the required JSON shape -- fails open to "wrote nothing
    this cycle" in both cases, never a malformed row."""
    beliefs = gather_synthesis_inputs(store)
    if not beliefs:
        return None

    try:
        response = llm.chat([{"role": "user", "content": _build_prompt(beliefs)}])
    except Exception:
        LOG.exception("[reflection-brain] LLM call failed, skipping this cycle")
        return None

    prediction = _extract_json_block(response.get("content", ""))
    if not prediction or not isinstance(prediction.get("maturity_profile"), dict):
        LOG.warning(
            "[reflection-brain] LLM response was not the required JSON shape, "
            "skipping this cycle rather than writing a malformed row",
        )
        return None

    action = prediction.get("proposed_action") or {}
    action_type = action.get("type")
    if action_type not in _VALID_ACTION_TYPES:
        action_type = None

    inputs_snapshot = [
        {
            "analyst_name": b["analyst_name"],
            "scope_type": b["scope_type"],
            "scope_key": b["scope_key"],
            "computed_at": b["computed_at"],
        }
        for b in beliefs
    ]

    return store.record_synthesis(
        trigger_reason=trigger_reason,
        inputs_snapshot=inputs_snapshot,
        prediction_json=prediction,
        proposed_action_type=action_type,
        resolution_criteria=_resolution_criteria_for(action) if action_type else "",
        resolve_by=time.time() + SYNTHESIS_RESOLUTION_WINDOW_DAYS * 86400,
        evidence_count_at_synthesis=sum(b.get("evidence_count", 0) for b in beliefs),
    )


def resolve_pending_syntheses(store: ReflectionStore) -> int:
    """Mechanically checks every past-due, unresolved synthesis against
    what `reflection_beliefs` actually shows now -- never a second LLM
    call grading the first one, which would just compound uncertainty on
    top of uncertainty. Only `threshold_nudge` predictions carry a
    mechanically checkable claim; every other action type (and any
    prediction with no proposed action at all) resolves `inconclusive`,
    honestly, rather than guessed. Returns how many rows were resolved."""
    resolved = 0
    for row in store.list_pending_syntheses():
        if row.get("proposed_action_type") != "threshold_nudge":
            store.resolve_synthesis(
                row["synthesis_id"],
                observed_outcome_json={"note": "action type has no mechanical resolution check"},
                outcome_match="inconclusive",
            )
            resolved += 1
            continue

        action = (row["prediction_json"] or {}).get("proposed_action") or {}
        target_analyst = action.get("target_analyst_name")
        target_scope_type = action.get("target_scope_type")
        target_scope_key = action.get("target_scope_key")
        belief = (
            store.get_belief(target_analyst, target_scope_type, target_scope_key)
            if target_analyst and target_scope_type and target_scope_key else None
        )

        if belief is None:
            outcome_match = "inconclusive"
            observed: dict[str, Any] = {"note": "target belief no longer exists"}
        else:
            snapshot_computed_at = next(
                (
                    s["computed_at"] for s in row["inputs_snapshot"]
                    if s["analyst_name"] == target_analyst and s["scope_type"] == target_scope_type
                    and s["scope_key"] == target_scope_key
                ),
                None,
            )
            if snapshot_computed_at is not None and belief["computed_at"] <= snapshot_computed_at:
                # No fresh non-routine write for this scope since the
                # synthesis -- write_finding() is never called again once a
                # scope returns to routine, so an unchanged computed_at IS
                # the real, mechanical signal that it did.
                outcome_match = "correct"
                observed = {"belief_severity_now": belief["severity"], "advanced_since_synthesis": False}
            elif belief["severity"] == "significant":
                outcome_match = "incorrect"
                observed = {"belief_severity_now": belief["severity"], "advanced_since_synthesis": True}
            else:
                outcome_match = "partially_correct"
                observed = {"belief_severity_now": belief["severity"], "advanced_since_synthesis": True}

        store.resolve_synthesis(row["synthesis_id"], observed_outcome_json=observed, outcome_match=outcome_match)
        resolved += 1
    return resolved
