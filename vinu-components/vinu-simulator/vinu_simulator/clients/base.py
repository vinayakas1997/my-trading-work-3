from __future__ import annotations

import threading
from typing import Any
from urllib.parse import urljoin

import httpx


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

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        resp = self._client().get(self._url(path), params=params)
        resp.raise_for_status()
        return resp.json()

    def post(self, path: str, json: dict[str, Any] | None = None) -> Any:
        resp = self._client().post(self._url(path), json=json)
        resp.raise_for_status()
        return resp.json()

    def close(self) -> None:
        client = getattr(self._local, "client", None)
        if client is not None:
            client.close()
