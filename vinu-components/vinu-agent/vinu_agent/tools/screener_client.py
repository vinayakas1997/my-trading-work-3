"""Fetches vinu-screener's current top-ranked symbols for a ranker, so
`bootstrap_new_tickers`'s seed list can include screener output alongside
the operator's static `VINU_AGENT_WATCHLIST_SEED_TICKERS`. Best-effort by
design, matching every other scheduled-worker step's contract: a screener
that's unreachable, not yet run, or errors must never stop the watchlist
bootstrap it's feeding into -- it just contributes nothing that cycle.
"""

from __future__ import annotations

import logging

LOG = logging.getLogger(__name__)


def fetch_screener_top_tickers(base_url: str, ranker_id: str, *, limit: int = 20) -> list[str]:
    import httpx

    try:
        from vinu_infra.auth import internal_auth_headers as _iah
        headers = _iah() or None
    except Exception:
        headers = None

    try:
        resp = httpx.get(
            f"{base_url.rstrip('/')}/screener/rankers/{ranker_id}/latest",
            headers=headers,
            timeout=15,
        )
        if resp.status_code == 404:
            LOG.info("screener ranker %s has no snapshot yet", ranker_id)
            return []
        resp.raise_for_status()
        data = resp.json()
        top = data.get("top", []) if isinstance(data, dict) else []
        symbols = [entry["symbol"] for entry in top if isinstance(entry, dict) and entry.get("symbol")]
        return symbols[:limit]
    except Exception:
        LOG.exception("fetching screener top tickers for ranker %s failed, continuing", ranker_id)
        return []
