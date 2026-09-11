"""Stage B (part of B10's pipeline shape): deterministic "near-score
rotation" for result diversity, ported from daily_stock_analysis
(`docs/screening-engine.md:86-90`). Without this, the same top-N candidates
would show up cycle after cycle whenever several symbols cluster tightly in
score -- not wrong, but stale-feeling for a human reading the shortlist.

DSA's own description, preserved here exactly because it's precise about
what this is *not*: a per-session seed perturbs only the candidates in the
bottom half of the shortlist that are within `band` score points of the
cutoff; hard-filtered/vetoed candidates and the top half (or any candidate
clearly above the band) are never touched. This is explicitly not random
re-scoring -- `final_score` itself is untouched; only the *tie-break order*
among near-score candidates changes, deterministically, for a given seed.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from .candidate import Candidate


@dataclass(frozen=True)
class RotationConfig:
    top_n: int
    band: float = 1.5           # DSA's own default -- "within 1.5 points of the cutoff"
    enabled: bool = True


def near_score_rotation(candidates: list[Candidate], cfg: RotationConfig, *, seed: int) -> list[Candidate]:
    """`candidates` must already be ranked (highest `final_score` first,
    ties broken however the caller likes) -- returns a new list, same
    membership, with only the near-cutoff tail reordered."""
    ranked = [c for c in candidates if c.alive]
    if not cfg.enabled or len(ranked) <= cfg.top_n:
        return ranked

    cutoff_score = ranked[cfg.top_n - 1].final_score
    protected: list[Candidate] = []
    perturbable: list[Candidate] = []
    half = len(ranked) // 2
    for idx, c in enumerate(ranked):
        # Perturbable only if it's in the bottom half of the whole ranked
        # list AND its score is within `band` of the cutoff -- everything
        # else (front half, or a bottom-half candidate far below the
        # cutoff) is protected and keeps its exact slot.
        if idx >= half and abs(c.final_score - cutoff_score) <= cfg.band:
            perturbable.append(c)
        else:
            protected.append(c)

    rng = random.Random(seed)
    rng.shuffle(perturbable)

    # Reassemble preserving each candidate's original relative slot family:
    # protected candidates keep their original relative order; perturbable
    # ones (all within `band` of the cutoff) are interleaved back into the
    # positions they vacated, shuffled.
    result: list[Candidate] = []
    protected_iter = iter(protected)
    perturbable_iter = iter(perturbable)
    protected_set = set(id(c) for c in protected)
    for c in ranked:
        if id(c) in protected_set:
            result.append(next(protected_iter))
        else:
            result.append(next(perturbable_iter))
    return result
