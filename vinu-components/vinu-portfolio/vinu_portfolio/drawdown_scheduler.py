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

LOG = logging.getLogger(__name__)


def run_once(monitor: PortfolioDrawdownMonitor, agent_api_url: str) -> dict[str, Any]:
    """One poll-and-check cycle. Returns a status dict for logging/testing."""
    try:
        resp = httpx.get(f"{agent_api_url}/agent/broker/account", timeout=10.0)
        resp.raise_for_status()
        account = resp.json()
    except Exception as e:
        LOG.warning("Could not fetch account equity from %s: %s", agent_api_url, e)
        return {"status": "unavailable", "error": str(e)}

    if not account.get("configured"):
        return {"status": "no_broker_account"}

    equity = account.get("equity")
    if equity is None:
        return {"status": "no_equity_data"}

    result = monitor.update(float(equity))
    return {"status": "checked", "equity": equity, **result}


def monitor_main_loop(config: PortfolioConfig | None = None) -> None:
    config = config or load_config()
    monitor = PortfolioDrawdownMonitor(
        drawdown_threshold=config.drawdown_halt_threshold,
        agent_api_url=config.agent_api_url,
    )
    LOG.info(
        "Starting portfolio drawdown monitor — threshold=%.1f%%, interval=%ds, agent_api=%s",
        config.drawdown_halt_threshold * 100, config.drawdown_monitor_interval_sec, config.agent_api_url,
    )
    while True:
        result = run_once(monitor, config.agent_api_url)
        LOG.info("Drawdown monitor cycle: %s", result)
        time.sleep(config.drawdown_monitor_interval_sec)
