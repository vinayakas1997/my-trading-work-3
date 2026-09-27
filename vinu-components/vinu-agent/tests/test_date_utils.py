"""item #11 finding #1: date_to_epoch/iso_to_epoch used to be copy-pasted
verbatim (and inconsistently -- date_to_epoch was local-timezone-dependent
via time.mktime, iso_to_epoch was explicitly UTC-aware) across
stock_price_tool.py, news_tool.py, correlation_tool.py, and
features_tool.py. Now one shared, UTC-aware module."""

from __future__ import annotations

from datetime import datetime, timezone

from vinu_agent.tools._date_utils import date_to_epoch, iso_to_epoch


class TestDateToEpoch:
    def test_parses_as_utc_midnight_not_local_time(self) -> None:
        expected = int(datetime(2025, 6, 1, tzinfo=timezone.utc).timestamp())
        assert date_to_epoch("2025-06-01") == expected

    def test_agrees_with_iso_to_epoch_for_the_same_utc_instant(self) -> None:
        """The exact inconsistency the finding named: these two are
        compared directly against each other in every caller's as-of
        clamp logic, so a date-only string and its midnight-UTC ISO
        equivalent must produce the identical epoch."""
        assert date_to_epoch("2025-06-01") == iso_to_epoch("2025-06-01T00:00:00Z")


class TestIsoToEpoch:
    def test_parses_z_suffix_as_utc(self) -> None:
        expected = int(datetime(2025, 6, 1, 12, 30, tzinfo=timezone.utc).timestamp())
        assert iso_to_epoch("2025-06-01T12:30:00Z") == expected

    def test_parses_explicit_offset(self) -> None:
        expected = int(datetime(2025, 6, 1, 12, 30, tzinfo=timezone.utc).timestamp())
        assert iso_to_epoch("2025-06-01T12:30:00+00:00") == expected
