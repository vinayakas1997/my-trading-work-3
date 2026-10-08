"""Reads the capital ledger from vinu-live (`GET /live/capital`): the real-money base, committed money and free cash.

One reader for every agent-side user (the order guard, the capital-allocator budget, the agent tool), so they all see the
same figures. Returns None when the ledger cannot be read; callers that spend money treat that as "refuse".
"""
from __future__ import annotations

import logging
import os
from typing import Any

import requests

LOG = logging.getLogger(__name__)
DEFAULT_LIVE_URL = "http://localhost:8091"


def fetch_capital_ledger(timeout: float = 5.0) -> dict[str, Any] | None:
    url = os.environ.get("VINU_LIVE_API_URL", DEFAULT_LIVE_URL)
    try:
        from vinu_infra.auth import internal_auth_headers

        headers = internal_auth_headers() or None
    except Exception:  # noqa: BLE001
        headers = None
    try:
        resp = requests.get(f"{url}/live/capital", headers=headers, timeout=timeout)
        if resp.status_code != 200:
            return None
        data = resp.json()
        return data if isinstance(data, dict) and data.get("status") == "ok" else None
    except Exception as e:  # noqa: BLE001
        LOG.warning("Capital ledger unavailable: %s", e)
        return None
