"""Phase 3's Kill-Switch gate on the rebalance-request path (New-talk-
agents/new-thinking/new-restructure/phases/phase-3-kill-switch/): a
rebalancer asking Monitor to unwind position X to fund candidate Y is an
order-flow-adjacent ACTION, and is blocked by the Kill Switch by default --
the same fail-closed-to-halted direction as capital_allocator's funding
gate (agent/capital_allocator_hook.py).

Deliberately does NOT gate Monitor's own read-only hold/decay comparison
-- only the request path a caller uses to ask for a position change. This
module has no other caller in the codebase yet: `capital_allocator`'s
rebalancer and `Monitor` (extending vinu-live's TradePlanOrchestrator) are
Phase 5's job, not built yet (New-talk-agents/new-thinking/
new-restructure/phases/phase-5-monitor-extend/, still flags "capital_
allocator's rebalancer needs an actual target to call -- confirmed
nowhere yet that one exists"). Built and tested now so Phase 5 has a
ready, already-correct gate to call rather than needing to re-derive the
fail-closed direction under time pressure later.
"""

from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


def check_rebalance_allowed(scope: str) -> bool:
    """True only if the Kill Switch is confirmed NOT engaged for `scope`
    (a ticker symbol -- the same convention pinned down for
    OrderGuard/capital_allocator_hook.py). Fail-closed: any uncertainty
    (the check itself errors) returns False, same direction as
    capital_allocator_hook.py's `_is_halted` -- this is a real-money-
    adjacent check, not a cost-only one."""
    try:
        from ..broker.kill_switch import is_trading_halted
        return not is_trading_halted(scope=scope)
    except Exception:
        LOG.exception("kill switch check failed for scope %r, denying rebalance request", scope)
        return False
