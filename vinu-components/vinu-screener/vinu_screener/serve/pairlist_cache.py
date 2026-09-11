"""Stage B (B20): `RemotePairList`'s bearer-token + TTL-cache +
fail-open-on-failure pattern (`freqtrade/plugins/pairlist/
RemotePairList.py`), applied to the *exposing* side rather than Freqtrade's
original consuming side -- `vinu-screener` is the source of a ranked
symbol list here, not the consumer of one, but the same three properties
matter for exactly the same reason: whatever calls this endpoint (another
Vina service, an operator's dashboard) shouldn't (a) need to re-run a full
pipeline cycle on every poll, (b) be unauthenticated, or (c) get a hard
error just because the *next* scheduled refresh happened to fail -- serving
the last-known-good list (`keep_pairlist_on_failure`'s own name) is safer
than serving nothing.

Bearer-token check matches Vina's existing runtime-settings admin API auth
model (same tracker note the source doc makes).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class CachedPairlist:
    symbols: list[str]
    generated_at: float
    stale: bool = False   # True when this is a fail-open replay of the last-good list


@dataclass
class PairlistCache:
    """One cached ranked list per rule_id. `refresh_fn(rule_id) ->
    list[str]` is supplied by the caller (a `ScreenPipeline.run()` wrapper,
    typically) -- this class owns only the TTL/fail-open bookkeeping around
    it, not how the list is actually produced."""

    refresh_fn: Callable[[str], list[str]]
    ttl_sec: float = 60.0
    _entries: dict[str, CachedPairlist] = field(default_factory=dict)

    def get(self, rule_id: str, *, now: float | None = None) -> CachedPairlist:
        now = now if now is not None else time.time()
        cached = self._entries.get(rule_id)
        if cached is not None and (now - cached.generated_at) < self.ttl_sec:
            return cached

        try:
            symbols = self.refresh_fn(rule_id)
        except Exception:  # noqa: BLE001 -- a refresh failure must fail open, not raise to the caller
            if cached is not None:
                return CachedPairlist(symbols=cached.symbols, generated_at=cached.generated_at, stale=True)
            raise  # no last-good list to fall back on -- nothing safe to serve

        fresh = CachedPairlist(symbols=symbols, generated_at=now, stale=False)
        self._entries[rule_id] = fresh
        return fresh

    def invalidate(self, rule_id: str | None = None) -> None:
        if rule_id is None:
            self._entries.clear()
        else:
            self._entries.pop(rule_id, None)


def check_bearer_token(header_value: str | None, expected_token: str) -> bool:
    """`Authorization: Bearer <token>` check -- a plain string comparison,
    matching the simplicity of Vina's other bearer-token checks rather than
    introducing a new auth posture (HMAC, constant-time compare, ...) just
    for this endpoint."""
    if not header_value or not header_value.startswith("Bearer "):
        return False
    return header_value[len("Bearer "):] == expected_token
