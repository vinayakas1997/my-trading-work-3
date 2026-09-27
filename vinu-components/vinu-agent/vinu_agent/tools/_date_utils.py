"""Shared date/epoch parsing for tool files that clamp fetches to an
as-of replay date -- item #11 finding #1. Previously copy-pasted
verbatim across stock_price_tool.py, news_tool.py, correlation_tool.py
(both helpers), and features_tool.py (date_to_epoch only), and already
inconsistent with each other before this: date_to_epoch went through
time.mktime(time.strptime(...)), which interprets the parsed struct_time
in the server's LOCAL timezone, while iso_to_epoch (used right alongside
it in the same as-of clamp checks) is explicitly UTC-aware. A server not
running in UTC could silently clamp an as-of boundary to the wrong
instant. Both are UTC-aware here so a clamp comparison between the two
is always apples-to-apples.
"""

from __future__ import annotations

from datetime import datetime, timezone


def date_to_epoch(date_str: str) -> int:
    dt = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def iso_to_epoch(iso: str) -> int:
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp())
