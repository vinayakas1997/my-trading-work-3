"""Scheduled loop feeding live account equity into PortfolioDrawdownMonitor.

Closes the gap left after status-4: the monitor and the halt transport
(agent-api's /broker/halt) both existed and were tested, but nothing ever
called monitor.update() with a real value. This is that caller.

Equity comes from agent-api's /broker/account rather than this service
holding its own broker credentials — one place owns the broker connection.
Before a broker account exists, that endpoint reports configured=False and
this loop simply logs and waits, which is expected, not an error.
"""

from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from vinu_portfolio.circuit_breakers import PortfolioDrawdownMonitor
from vinu_portfolio.config import PortfolioConfig, load_config
from vinu_portfolio.storage.drawdown_status import DrawdownStatusStore

LOG = logging.getLogger(__name__)


def run_once(
    monitor: PortfolioDrawdownMonitor,
    agent_api_url: str,
    store: DrawdownStatusStore | None = None,
) -> dict[str, Any]:
    """One poll-and-check cycle. Returns a status dict for logging/testing.

    `store` (item #23 findings #2/#3 fix): when provided, this cycle's
    real `action` is written through to the same on-disk file
    `PortfolioService.compute_daily_allocation()` reads, so the halve/
    flat/halt state this monitor computes actually reaches sizing instead
    of being a value nothing downstream ever read. Optional so existing
    callers/tests that don't care about this wiring are unaffected.
    """
    try:
        try:
            from vinu_infra.auth import internal_auth_headers
            _headers = internal_auth_headers() or None
        except Exception:
            _headers = None
        resp = httpx.get(f"{agent_api_url}/agent/broker/account", headers=_headers, timeout=10.0)
        resp.raise_for_status()
        account = resp.json()
    except Exception as e:
        LOG.warning("Could not fetch account equity from %s: %s", agent_api_url, e)
        # item #23 finding #4: this used to be the end of the story --
        # log and move on, no retry/backoff, no escalation. An extended
        # outage now escalates to a real halt once it persists (see
        # PortfolioDrawdownMonitor.note_unavailable's own docstring), and
        # that action reaches the store too, so sizing doesn't keep
        # reading a stale "ok" from before the outage began.
        unavailable_result = monitor.note_unavailable()
        if store is not None:
            store.record(
                action=unavailable_result["action"], current_drawdown=0.0,
                threshold_breached=unavailable_result["escalated_halt"],
            )
        return {"status": "unavailable", "error": str(e), **unavailable_result}

    if not account.get("configured"):
        return {"status": "no_broker_account"}

    equity = account.get("equity")
    if equity is None:
        return {"status": "no_equity_data"}

    result = monitor.update(float(equity))
    if store is not None:
        store.record(
            action=result["action"], current_drawdown=result["current_drawdown"],
            threshold_breached=result["threshold_breached"],
        )
    return {"status": "checked", "equity": equity, **result}


def monitor_main_loop(config: PortfolioConfig | None = None) -> None:
    config = config or load_config()
    monitor = PortfolioDrawdownMonitor(
        drawdown_threshold=config.drawdown_halt_threshold,
        agent_api_url=config.agent_api_url,
        abs_loss_threshold=config.abs_loss_halt_threshold or None,
    )
    store = DrawdownStatusStore(str(config.data_root / "drawdown_status.db"))
    LOG.info(
        "Starting portfolio drawdown monitor — threshold=%.1f%%, abs_loss_halt=%.1f%%, "
        "interval=%ds, agent_api=%s",
        config.drawdown_halt_threshold * 100, config.abs_loss_halt_threshold * 100,
        config.drawdown_monitor_interval_sec, config.agent_api_url,
    )
    try:
        while True:
            result = run_once(monitor, config.agent_api_url, store=store)
            LOG.info("Drawdown monitor cycle: %s", result)
            time.sleep(config.drawdown_monitor_interval_sec)
    finally:
        store.close()
