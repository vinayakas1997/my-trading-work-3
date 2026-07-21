from __future__ import annotations

import logging
import threading
import time
from typing import Any

import httpx

from vinu_lib.retry import TransientProviderError

LOG = logging.getLogger(__name__)

_REATTEMPTS = 3
_BACKOFF = 1.5


class BaseClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._client = httpx.Client(timeout=timeout)
        self._lock = threading.Lock()

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        delay = 1.0
        for attempt in range(_REATTEMPTS):
            try:
                with self._lock:
                    resp = getattr(self._client, method)(url, **kwargs)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise TransientProviderError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, TransientProviderError) as e:
                if attempt == _REATTEMPTS - 1:
                    LOG.warning("HTTP error on %s %s (exhausted %s attempts): %s",
                                method.upper(), url, _REATTEMPTS, e)
                    return {}
                LOG.warning("Transient error on %s %s (attempt %s/%s): %s",
                            method.upper(), url, attempt + 1, _REATTEMPTS, e)
                time.sleep(delay)
                delay *= _BACKOFF
            except httpx.HTTPError as e:
                LOG.warning("HTTP error on %s %s (status %s): %s",
                            method.upper(), url,
                            getattr(e.response, "status_code", "?"), e)
                return {}
            except Exception as e:
                LOG.error("Unexpected error on %s %s: %s", method.upper(), url, e)
                return {}
        return {}

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        return self._request("get", path, params=params)

    def _post(self, path: str, json: dict[str, Any] | None = None) -> dict[str, Any] | list[Any]:
        return self._request("post", path, json=json)
