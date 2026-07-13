"""Tests for response_validator."""

from vinu_news.rss.fetch.response_validator import is_valid_feed_body


def test_rejects_html_cloaking():
    body = b"<html><head><title>Blocked</title></head><body>Access denied by firewall</body></html>"
    valid, reason = is_valid_feed_body(body)
    assert valid is False
    assert reason == "html_cloaking_detected"


def test_rejects_doctype_html():
    body = b"<!DOCTYPE html><html><body>Access denied</body></html>"
    valid, reason = is_valid_feed_body(body)
    assert valid is False
    assert reason == "html_cloaking_detected"


def test_rejects_too_short():
    valid, reason = is_valid_feed_body(b"<rss></rss>")
    assert valid is False
    assert reason == "body_too_short"


def test_accepts_valid_rss_prefix():
    body = b"<?xml version='1.0'?><rss version='2.0'><channel><title>Test</title></channel></rss>"
    valid, reason = is_valid_feed_body(body)
    assert valid is True
    assert reason == "ok"
