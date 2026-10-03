"""item #16 finding #3 (missing-pieces-of-system/new-theory-of-trading/
system-wide-audit-and-design/02-open-questions-strategy-and-simulation.md):
"a unified candidate graveyard is needed, not three separate,
disconnected rejection mechanisms." An idea can currently die at
generation-time (`GenerationCandidateStore`, item #16 finding #2),
sweep-time (`SweepGridStore`, item #3), or hypothesis-level
(`HypothesisRegistry.reject_with_reason()`, items #1/#7). Structurally
these are the same fact -- "this was tried, here's why it didn't
survive" -- but each lives in its own store with its own shape, so the
system can't currently ask "has something like this already failed, and
why" across all three at once.

This is deliberately a read-time query across the three existing stores,
not a fourth table: none of them change what they record, and nothing
here re-attributes a generation-discard to look like a sweep-failure or
vice versa (each entry keeps its own `source` tag and identifiers) --
just a way to ask about all three together. `code_hash` is the one
identifier that links a generation-time discard to a later sweep of the
"same" candidate. That join is now made (the-inconsistencies-v2 plan
2.4c, v1 A4): a base-code-mode sweep stores the hash of the base code it
varied (`sweep_runs.base_code_hash`, same `code_hash` function the
generation store uses), so a discarded generation candidate lists the
sweeps that later varied it (`swept_in`), and a failed sweep point lists
the generation rounds that produced its base code (`generation_ids`).
Recipe-mode sweeps have no base code and never join. Read-only: nothing
here blocks a candidate (a graveyard-as-gate is still a separate decision).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from vinu_research.generation_candidate_store import GenerationCandidateStore
from vinu_research.hypothesis_registry import HypothesisRegistry
from vinu_research.models import HypothesisStatus
from vinu_research.sweep_store import SweepGridStore


def _epoch_to_iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def query_candidate_graveyard(
    symbol: str,
    *,
    generation_store: GenerationCandidateStore,
    sweep_store: SweepGridStore,
    hypothesis_registry: HypothesisRegistry | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """One combined, time-ordered (most recent first) list across all
    three death points for this symbol. `created_at` is normalized to ISO
    8601 UTC across all three sources (generation/sweep store natively
    record epoch floats, HypothesisRegistry natively records ISO
    strings) so a single sort/compare works without a type error --
    display-only normalization, the underlying stores are untouched.

    `hypothesis_registry=None` skips that source entirely rather than
    constructing a default-path one here -- callers that already hold a
    registry instance (or a test double) should pass it explicitly, same
    "don't construct a second, possibly-diverging instance" reasoning as
    every other store this pattern touches.
    """
    entries: list[dict[str, Any]] = []

    for round_ in generation_store.list_rounds(symbol=symbol, limit=limit):
        detail = generation_store.get_round(round_["generation_id"])
        if detail is None:
            continue
        created_at = _epoch_to_iso(round_["created_at"])
        for c in detail["candidates"]:
            if c["chosen"]:
                continue  # the winner isn't a graveyard entry
            entries.append({
                "source": "generation",
                "symbol": symbol,
                "identifier": c["code_hash"],
                "reason": c["reasoning_excerpt"] or "discarded by heuristic complexity-penalty ranking",
                "created_at": created_at,
                "generation_id": round_["generation_id"],
                "swept_in": [
                    {k: sw[k] for k in ("sweep_id", "requested", "succeeded", "completeness")}
                    for sw in sweep_store.find_sweeps_by_base_code_hash(c["code_hash"])
                ],
            })

    for sweep in sweep_store.list_sweeps(symbol=symbol, limit=limit):
        detail = sweep_store.get_sweep(sweep["sweep_id"])
        if detail is None:
            continue
        created_at = _epoch_to_iso(sweep["created_at"])
        base_hash = detail.get("base_code_hash")
        generation_ids = (
            sorted({g["generation_id"] for g in generation_store.find_by_code_hash(base_hash)})
            if base_hash else []
        )
        for p in detail["points"]:
            if p["succeeded"]:
                continue
            entries.append({
                "source": "sweep",
                "symbol": symbol,
                "identifier": p["run_id"] or "",
                "reason": p["failure_reason"] or "backtest failed",
                "created_at": created_at,
                "sweep_id": sweep["sweep_id"],
                "params": p["params"],
                "param_diff_from_winner": p.get("param_diff_from_winner"),
                "generation_ids": generation_ids,
            })

    if hypothesis_registry is not None:
        for h in hypothesis_registry.query_by_symbol(symbol, status=HypothesisStatus.rejected):
            entries.append({
                "source": "hypothesis",
                "symbol": symbol,
                "identifier": h.hypothesis_id,
                "reason": h.invalidation_reason or "rejected, no reason recorded",
                "created_at": h.updated_at,
                "hypothesis_id": h.hypothesis_id,
            })

    entries.sort(key=lambda e: e["created_at"], reverse=True)
    return entries[:limit]
