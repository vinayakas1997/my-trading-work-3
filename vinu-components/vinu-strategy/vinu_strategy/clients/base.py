from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from vinu_infra.retry import TransientProviderError

LOG = logging.getLogger(__name__)

_REATTEMPTS = 3
_BACKOFF = 1.5


class BaseClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        try:
            from vinu_infra.auth import internal_auth_headers
            headers = internal_auth_headers() or None
        except Exception:
            headers = None
        self._client = httpx.Client(timeout=timeout, headers=headers)

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any] | list[Any]:
        url = f"{self._base_url}{path}"
        delay = 1.0
        for attempt in range(_REATTEMPTS):
            try:
                # item #22 finding #7: a shared threading.Lock() used to
                # wrap this call's full network round-trip -- with
                # FeaturesClient/CorrelationClient each a single instance
                # shared across service.py's _MAX_WORKERS=10 executor,
                # that serialized every concurrent symbol fetch through
                # one call at a time regardless of the thread pool,
                # buying almost nothing from the concurrency it looked
                # like it enabled. httpx.Client is documented thread-safe
                # for concurrent requests (its own internal connection
                # pool handles this) -- dropped rather than switching to
                # one client per worker, since a single shared client's
                # pooled connections are strictly more resource-efficient
                # than 10 separate pools for the same upstream service.
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
