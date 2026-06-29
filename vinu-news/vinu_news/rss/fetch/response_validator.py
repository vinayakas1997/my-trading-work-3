"""Response validation — Fincept HTML cloaking detection."""

from vinu_news.rss.config.settings import HTML_CLOAK_PREFIX_LEN, MIN_BODY_BYTES


def is_valid_feed_body(body: bytes) -> tuple[bool, str]:
    """Return (valid, reason). Reject HTML captcha/block pages."""
    if not body:
        return False, "empty_body"

    if len(body) < MIN_BODY_BYTES:
        return False, "body_too_short"

    prefix = body[:HTML_CLOAK_PREFIX_LEN].lower().lstrip()
    if prefix.startswith(b"<html") or prefix.startswith(b"<!doctype html"):
        return False, "html_cloaking_detected"

    return True, "ok"
