"""Fetches currently-held symbols from vinu-agent's broker positions, so
RankerRunner.run()'s held_symbols param can be populated with real data
(see risk_overlay.py's already_held RiskCheck). Best-effort by design,
same posture as vinu_agent/tools/screener_client.py (the reverse-direction
counterpart): a portfolio service that's unreachable or not configured
must never stop a ranking run -- it just contributes no held-symbol
awareness that cycle.
"""

from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


def fetch_held_symbols(base_url: str) -> frozenset[str]:
    if not base_url:
        return frozenset()

    import httpx

    try:
        resp = httpx.get(f"{base_url.rstrip('/')}/agent/broker/positions", timeout=15)
        resp.raise_for_status()
        data = resp.json()
        positions = data if isinstance(data, list) else []
        return frozenset(
            str(p["symbol"]).upper() for p in positions if isinstance(p, dict) and p.get("symbol")
        )
    except Exception:
        LOG.warning("fetching held symbols from %s failed, continuing without them", base_url, exc_info=True)
        return frozenset()
