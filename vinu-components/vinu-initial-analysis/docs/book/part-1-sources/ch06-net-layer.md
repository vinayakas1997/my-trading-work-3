# Chapter 06 — HTTP net layer & Docker fallback

| Field | Value |
|-------|-------|
| **Package** | vinu-correlation |
| **Module** | `vinu_correlation/net.py` |
| **Status** | DRAFT |
| **Prerequisites** | ch03 |

## 1. Problem

When vinu-correlation runs inside a Docker container, it cannot reach the host's `127.0.0.1` services. The net layer transparently retries failed connections against `host.docker.internal`.

## 2. Logic

```python
def request(method, url, **kwargs):
    try:
        return requests.request(method, url, **kwargs)
    except ConnectionError:
        fallback = _docker_fallback_url(url)  # 127.0.0.1 -> host.docker.internal
        if fallback is None:
            raise
        return requests.request(method, fallback, **kwargs)
```

Only loopback hosts (`localhost`, `127.0.0.1`) are eligible for fallback.

## 3. Tests

| Test file | Asserts |
|-----------|---------|
| (no dedicated unit test — covered by integration) | |
