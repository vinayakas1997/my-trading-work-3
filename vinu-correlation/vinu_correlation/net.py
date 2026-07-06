from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

LOG = logging.getLogger(__name__)
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}


def _docker_fallback_url(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.hostname not in _LOOPBACK_HOSTS:
        return None
    netloc = "host.docker.internal"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    try:
        return requests.request(method, url, **kwargs)
    except requests.ConnectionError as e:
        if "Connection refused" not in str(e):
            raise
        fallback_url = _docker_fallback_url(url)
        if fallback_url is None:
            raise
        LOG.debug("Retrying against host.docker.internal: %s -> %s", url, fallback_url)
        return requests.request(method, fallback_url, **kwargs)
