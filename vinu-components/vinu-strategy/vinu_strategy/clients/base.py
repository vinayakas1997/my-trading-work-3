from __future__ import annotations

import logging
import threading
from typing import Any

import httpx

LOG = logging.getLogger(__name__)


class BaseClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)
        self._lock = threading.Lock()

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        try:
            with self._lock:
                resp = self._client.get(url, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            LOG.warning("HTTP error fetching %s: %s", url, e)
            return {}
        except Exception as e:
            LOG.error("Unexpected error fetching %s: %s", url, e)
            return {}

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        try:
            with self._lock:
                resp = self._client.post(url, json=json)
            resp.raise_for_status()
            return resp.json()
        except httpx.HTTPError as e:
            LOG.warning("HTTP error posting %s: %s", url, e)
            return {}
        except Exception as e:
            LOG.error("Unexpected error posting %s: %s", url, e)
            return {}
