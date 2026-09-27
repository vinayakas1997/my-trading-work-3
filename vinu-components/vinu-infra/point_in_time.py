"""Shared server-side as-of enforcement -- item #21 pattern #1 (system-
wide-audit-and-design/02-open-questions-strategy-and-simulation.md):
"the single property this entire design depends on most -- no
look-ahead bias -- is currently enforced nowhere except caller
discipline" at the two places raw data enters the whole system
(vinu-stock-price, vinu-news). Both had server-side reads with no cap
against a replay `as_of` boundary at all; only vinu-agent's tool-layer
code remembered to clamp client-side, with nothing to catch a future
caller that forgets.

One shared, tested function here, called explicitly from each affected
route -- not a decorator/middleware. The two services' existing routes
already differ in shape (`to`/`from`/`days` here, `to`/`from`/`limit`
there) enough that a generic wrapper would need to special-case each one
anyway; a plain function call at the one place each route already
computes its effective end-of-range achieves the same "no per-service
reinvention" goal with far less framework-level risk than threading a
new decorator through two independent FastAPI apps.
"""

from __future__ import annotations


def clamp_to_as_of(value: int | None, as_of: int | None) -> tuple[int | None, bool]:
    """Caps `value` (typically a computed `to_ts` end-of-range) at
    `as_of` when it would otherwise exceed it.

    `as_of=None` means no replay boundary was requested at all -- returns
    `value` unchanged, never substituting "now" implicitly (a caller that
    wants a "now" ceiling passes it explicitly, same as every other
    as-of-aware call site in this codebase). `value=None` with an
    `as_of` set means the caller didn't ask for an explicit end at
    all -- returns `as_of` itself as the effective end, not `None`
    (an unbounded query is exactly the gap this closes), and reports
    that as a clamp since the caller's effective range changed.

    Returns `(effective_value, was_clamped)`.
    """
    if as_of is None:
        return value, False
    if value is None:
        return as_of, True
    if value > as_of:
        return as_of, True
    return value, False
