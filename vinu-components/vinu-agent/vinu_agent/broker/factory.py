"""The one real decision point for "which broker provider" (`broker/base.py`'s
`Broker` Protocol is the contract; this is where a provider name turns
into a real instance). Alpaca stays the default -- `VINU_AGENT_BROKER_
PROVIDER` unset or "alpaca" both resolve to it, so every existing
deployment keeps working unchanged. Adding a second real provider later
is: implement `Broker`'s methods, add one line to `_PROVIDERS`, done --
no call site anywhere else needs to change again, since every one of them
already goes through `get_live_broker()` instead of importing
`AlpacaBroker` directly.

Deliberately excludes `HistoricalFillBroker` -- that's selected by
`as_of` being set (a replay session), independent of which real provider
is configured, and is handled by each call site's own existing
`as_of`-branching (`_build_broker`/`_make_broker` helpers in
`audit/ground_truth.py`, `tools/portfolio_tool.py`, `tools/trade_tool.py`
already did this before this module existed -- untouched here).
"""

from __future__ import annotations

import os
from typing import Callable

from .alpaca import AlpacaBroker
from .base import Broker

_PROVIDERS: dict[str, Callable[[], Broker]] = {
    "alpaca": AlpacaBroker,
}

DEFAULT_PROVIDER = "alpaca"


def get_live_broker(provider: str | None = None) -> Broker:
    """The real (non-replay) broker for the configured provider. `provider`
    is an explicit override for callers/tests that need one; production
    code should normally omit it and let VINU_AGENT_BROKER_PROVIDER (or
    the default) decide."""
    name = (provider or os.environ.get("VINU_AGENT_BROKER_PROVIDER", DEFAULT_PROVIDER)).strip().lower()
    try:
        constructor = _PROVIDERS[name]
    except KeyError:
        available = ", ".join(sorted(_PROVIDERS))
        raise ValueError(f"Unknown broker provider {name!r} (VINU_AGENT_BROKER_PROVIDER) -- available: {available}") from None
    return constructor()
