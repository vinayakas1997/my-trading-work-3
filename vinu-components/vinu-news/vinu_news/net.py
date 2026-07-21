"""HTTP helper: retries a loopback URL via host.docker.internal.

.env is shared between local runs (where 127.0.0.1/localhost reaches
sibling services directly) and Docker Compose (where loopback means the
container itself). Rather than maintaining separate .env files per
environment, retry once against host.docker.internal when the configured
loopback host refuses the connection.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import requests

LOG = logging.getLogger(__name__)
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1"}
_REATTEMPTS = 3
_BACKOFF = 1.5


def _docker_fallback_url(url: str) -> str | None:
    parts = urlsplit(url)
    if parts.hostname not in _LOOPBACK_HOSTS:
        return None
    netloc = "host.docker.internal"
    if parts.port:
        netloc = f"{netloc}:{parts.port}"
    return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))


def request(method: str, url: str, **kwargs: Any) -> requests.Response:
    """requests.request(), retried against host.docker.internal if `url`
    points at a loopback host that refuses the connection."""
    delay = 1.0
    last_exc: Exception | None = None
    for attempt in range(_REATTEMPTS):
        try:
            resp = requests.request(method, url, **kwargs)
            if resp.status_code in (429, 500, 502, 503, 504):
                last_exc = requests.HTTPError(f"HTTP {resp.status_code}", response=resp)
                if attempt == _REATTEMPTS - 1:
                    raise last_exc
                LOG.warning("Transient error on %s %s (attempt %s/%s): HTTP %s",
                            method.upper(), url, attempt + 1, _REATTEMPTS, resp.status_code)
                time.sleep(delay)
                delay *= _BACKOFF
                continue
            resp.raise_for_status()
            return resp
        except (requests.Timeout, requests.ConnectionError) as e:
            last_exc = e
            if (attempt == 0 and isinstance(e, requests.ConnectionError)
                    and "Connection refused" in str(e)):
                fallback_url = _docker_fallback_url(url)
                if fallback_url is not None:
                    LOG.debug("Trying Docker fallback: %s -> %s", url, fallback_url)
                    url = fallback_url
                    continue
            if attempt == _REATTEMPTS - 1:
                raise
            LOG.warning("Transient error on %s %s (attempt %s/%s): %s",
                        method.upper(), url, attempt + 1, _REATTEMPTS, e)
            time.sleep(delay)
            delay *= _BACKOFF
    raise last_exc  # type: ignore[misc]