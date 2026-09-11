"""Stage B (part of B10's pipeline shape): portfolio/sector concentration
overlay, ported from daily_stock_analysis's `risk.py:86-138,250-268`. A
factor-scored, risk-adjusted shortlist can still be one crowded trade --
five banks near the top of the list isn't diversification just because each
one individually scored well. This overlay walks the ranked candidates in
score order and applies a graduated penalty to each *repeat* visit to a
sector/theme bucket already represented among the picks ahead of it, so a
strong second-best candidate in an already-well-represented sector drops
behind a strong candidate from an under-represented one, rather than being
excluded outright (concentration is a soft, graduated cap here -- a hard
per-sector cap belongs to `vinu-portfolio`'s allocation stage, not this
screener-side overlay; see `rescale_correlated_clusters` there for that).

DSA's alias canonicalization (e.g. brokers/banks/insurance -> one "financial"
bucket) is represented here as an ordinary `bucket_map` the caller supplies
-- this module doesn't hardcode any taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .candidate import Candidate


@dataclass(frozen=True)
class ConcentrationConfig:
    bucket_map: dict[str, str] = field(default_factory=dict)   # sector/theme -> canonical bucket name
    penalty_per_repeat: float = 3.0     # applied to the 2nd, 3rd, ... pick in the same bucket
    max_penalty: float = 15.0           # capped per candidate, same "bounded" posture as the risk overlay


def _bucket_of(candidate: Candidate, cfg: ConcentrationConfig) -> str | None:
    if not candidate.sector:
        return None
    return cfg.bucket_map.get(candidate.sector, candidate.sector)


def apply_concentration_overlay(candidates: list[Candidate], cfg: ConcentrationConfig) -> None:
    """In-place: sets `concentration_penalty` on each alive candidate,
    ranked by its *current* `final_score` (factor score minus risk penalty)
    walked highest-first, so the top pick in a bucket is never penalized --
    only subsequent picks that would otherwise crowd the same bucket."""
    seen_counts: dict[str, int] = {}
    ranked = sorted((c for c in candidates if c.alive), key=lambda c: c.final_score, reverse=True)
    for candidate in ranked:
        bucket = _bucket_of(candidate, cfg)
        if bucket is None:
            continue
        count_before = seen_counts.get(bucket, 0)
        seen_counts[bucket] = count_before + 1
        if count_before == 0:
            continue  # first pick in this bucket -- unpenalized
        candidate.concentration_penalty = min(count_before * cfg.penalty_per_repeat, cfg.max_penalty)
