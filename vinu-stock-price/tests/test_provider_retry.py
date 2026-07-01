"""Tests for provider retry (TASK-S03)."""

import pytest
import requests

from vinu_stock.providers.retry import http_get_with_retry


def test_http_get_with_retry_succeeds_after_transient(monkeypatch):
    calls = {"n": 0}

    class FakeResp:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {}

    def fake_get(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] < 2:
            raise requests.Timeout("timeout")
        return FakeResp()

    monkeypatch.setattr(requests, "get", fake_get)
    resp = http_get_with_retry("http://example.com", n=3, backoff=0.01)
    assert resp.status_code == 200
    assert calls["n"] == 2
