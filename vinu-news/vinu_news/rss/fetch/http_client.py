"""HTTP client with Fincept 4-second timeout."""

import time

import requests

from vinu_news.rss.config.settings import REQUEST_TIMEOUT_SEC, USER_AGENT
from vinu_news.rss.fetch.fetch_result import FetchResult


def fetch_url(url: str) -> FetchResult:
    """GET url with timeout; return body and metadata."""
    start = time.perf_counter()
    headers = {"User-Agent": USER_AGENT}

    try:
        response = requests.get(
            url,
            timeout=REQUEST_TIMEOUT_SEC,
            headers=headers,
        )
        duration_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            status_code=response.status_code,
            body=response.content,
            error=None if response.ok else f"http_{response.status_code}",
            duration_ms=duration_ms,
        )
    except requests.Timeout:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            status_code=None,
            body=b"",
            error="timeout",
            duration_ms=duration_ms,
        )
    except requests.RequestException as exc:
        duration_ms = int((time.perf_counter() - start) * 1000)
        return FetchResult(
            url=url,
            status_code=None,
            body=b"",
            error=str(exc),
            duration_ms=duration_ms,
        )
