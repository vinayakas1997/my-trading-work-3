"""Live tests assume a regular-session Wednesday unless a test says otherwise: order routing depends on the session
(outside it only limit orders are sent), and a test run at night must not change what the older tests expect."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

REGULAR_WEDNESDAY = datetime(2026, 10, 7, 11, 0, tzinfo=ZoneInfo("America/New_York")).timestamp()


@pytest.fixture(autouse=True)
def _regular_session(monkeypatch):
    monkeypatch.setattr("vinu_live.trade_plan.guards._now", lambda: REGULAR_WEDNESDAY)
