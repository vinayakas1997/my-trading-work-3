from __future__ import annotations

import logging
import threading
import time
from typing import Any
from urllib.parse import urljoin

import httpx

from vinu_lib.retry import TransientProviderError

LOG = logging.getLogger(__name__)

_REATTEMPTS = 3
_BACKOFF = 1.5


class BaseClient:
    def __init__(self, base_url: str, timeout: float = 30.0):
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._local = threading.local()

    def _client(self) -> httpx.Client:
        if not hasattr(self._local, "client"):
            self._local.client = httpx.Client(timeout=self._timeout)
        return self._local.client

    def _url(self, path: str) -> str:
        return urljoin(self._base_url + "/", path.lstrip("/"))

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        delay = 1.0
        for attempt in range(_REATTEMPTS):
            try:
                resp = getattr(self._client(), method)(self._url(path), **kwargs)
                if resp.status_code in (429, 500, 502, 503, 504):
                    raise TransientProviderError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                return resp.json()
            except (httpx.TimeoutException, httpx.ConnectError, TransientProviderError) as e:
                if attempt == _REATTEMPTS - 1:
                    LOG.warning("HTTP error on %s %s (exhausted %s attempts): %s",
                                method.upper(), self._url(path), _REATTEMPTS, e)
                    raise
                LOG.warning("Transient error on %s %s (attempt %s/%s): %s",
                            method.upper(), self._url(path), attempt + 1, _REATTEMPTS, e)
                time.sleep(delay)
                delay *= _BACKOFF

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        return self._request("get", path, params=params)

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        return self._request("post", path, json=json)

    def close(self) -> None:
        client = getattr(self._local, "client", None)
        if client is not None:
            client.close()
