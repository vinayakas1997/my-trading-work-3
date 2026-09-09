"""Daily-ish refresh of the event calendar.

Called opportunistically from the ingest worker loop every cycle; it does real
work only when the last successful pull for a `kind` is older than
`min_interval_hours`. One Finnhub batch per day, triggered by a loop that is
already running -- no separate scheduler.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from vinu_stock.events.finnhub_provider import FinnhubCalendarProvider
from vinu_stock.events.store import EventsStore

LOG = logging.getLogger(__name__)


def refresh_calendar(
    store: EventsStore,
    provider: FinnhubCalendarProvider,
    symbols: list[str],
    *,
    macro_enabled: bool = True,
    min_interval_hours: float = 20.0,
    lookahead_days: int = 30,
) -> dict[str, Any]:
    """Refresh any calendar `kind` whose last pull is stale. Never raises: a
    provider error leaves the existing rows in place and is reported in the
    return dict. Returns {"refreshed": [...], "skipped": "...", ...}."""
    if not provider.is_configured():
        return {"refreshed": [], "skipped": "FINNHUB_API_KEY not set"}

    now = time.time()
    window = min_interval_hours * 3600.0
    to_epoch = now + lookahead_days * 86400.0
    refreshed: list[str] = []
    errors: dict[str, str] = {}

    if now - store.get_last_pull("earnings") >= window:
        try:
            recs = provider.get_earnings(symbols, now, to_epoch)
            n = store.replace_kind("earnings", recs)
            store.set_last_pull("earnings", now)
            refreshed.append("earnings")
            LOG.info("Events: earnings calendar refreshed (%d rows, %d symbols)", n, len(symbols))
        except Exception as e:  # noqa: BLE001 -- keep the loop alive, keep old rows
            errors["earnings"] = str(e)
            LOG.warning("Events: earnings refresh failed, keeping existing rows: %s", e)

    if macro_enabled and now - store.get_last_pull("economic") >= window:
        try:
            recs = provider.get_economic(now, to_epoch)
            n = store.replace_kind("economic", recs)
            store.set_last_pull("economic", now)
            refreshed.append("economic")
            LOG.info("Events: economic calendar refreshed (%d rows)", n)
        except Exception as e:  # noqa: BLE001
            errors["economic"] = str(e)
            LOG.warning("Events: economic refresh failed, keeping existing rows: %s", e)

    out: dict[str, Any] = {"refreshed": refreshed}
    if errors:
        out["errors"] = errors
    return out
