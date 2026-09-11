"""Stage B (B14): turnover-limiting `n_drop`/`hold_thresh`, ported from
Qlib's `TopkDropoutStrategy` (`qlib/contrib/strategy/signal_strategy.py:
75-298`). A screener re-ranks every cycle; without a turnover limit, a
candidate list can flip-flop symbol-for-symbol between adjacent cycles
whenever two candidates' scores cross near the cutoff -- noisy for a human
watching the shortlist, and (in Qlib's original portfolio-strategy context)
expensive for anything that actually trades the list.

`hold_thresh` is a minimum number of cycles a symbol stays in the held set
once admitted, even if a fresh rank would drop it -- a whipsaw guard.
`n_drop` caps how many currently-held symbols can be dropped in a single
cycle regardless of how many the fresh ranking would drop, so one volatile
cycle can't empty the whole list at once. Freed slots (from symbols that
were actually dropped) are filled from the fresh ranking's best
not-currently-held candidates, in order.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class TurnoverConfig:
    top_n: int
    n_drop: int | None = None     # None == no cap, drop as many as the fresh ranking would
    hold_thresh: int = 0          # cycles a symbol must stay held before it's eligible to be dropped


@dataclass
class TurnoverState:
    held: list[str] = field(default_factory=list)          # currently held, in the order admitted
    hold_cycles: dict[str, int] = field(default_factory=dict)  # symbol -> consecutive cycles held


def apply_turnover_gate(ranked_symbols: list[str], state: TurnoverState, cfg: TurnoverConfig) -> list[str]:
    """`ranked_symbols` is this cycle's fresh ranking, best-first (already
    past hard filter/risk/concentration/rotation). Mutates `state` in place
    and returns the resulting held list, best-first. Call once per cycle,
    same object each time -- `TurnoverState` is the per-rule turnover
    memory, analogous to `CooldownGate`'s per-(rule, symbol) `FireState`."""
    fresh_rank = {s: i for i, s in enumerate(ranked_symbols)}
    top_n_fresh = set(ranked_symbols[: cfg.top_n])

    # Candidates for dropping: currently held, no longer in the fresh top-N,
    # AND past their minimum hold time.
    droppable = [
        s for s in state.held
        if s not in top_n_fresh and state.hold_cycles.get(s, 0) >= cfg.hold_thresh
    ]
    n_drop = len(droppable) if cfg.n_drop is None else min(cfg.n_drop, len(droppable))
    # Drop the weakest-ranked (or entirely absent -> treated as worst) first.
    droppable.sort(key=lambda s: fresh_rank.get(s, len(ranked_symbols)), reverse=True)
    to_drop = set(droppable[:n_drop])

    survivors = [s for s in state.held if s not in to_drop]
    free_slots = cfg.top_n - len(survivors)
    admits = [s for s in ranked_symbols if s not in survivors][: max(free_slots, 0)]

    new_held = survivors + admits
    new_hold_cycles: dict[str, int] = {}
    for s in new_held:
        new_hold_cycles[s] = state.hold_cycles.get(s, 0) + 1 if s in survivors else 1

    state.held = new_held
    state.hold_cycles = new_hold_cycles
    # Keep held symbols in fresh-rank order for display, undropped-but-
    # currently-unranked symbols (shouldn't normally happen) sink to the end.
    return sorted(new_held, key=lambda s: fresh_rank.get(s, len(ranked_symbols)))
