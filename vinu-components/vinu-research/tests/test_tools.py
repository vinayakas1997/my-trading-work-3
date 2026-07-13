from __future__ import annotations

from vinu_research.tools import timestamps_from_dates


class TestTimestampsFromDates:
    def test_returns_tuple_of_ints(self):
        from_ts, to_ts = timestamps_from_dates("2024-01-01", "2024-12-31")
        assert isinstance(from_ts, int)
        assert isinstance(to_ts, int)
        assert from_ts < to_ts

    def test_known_date(self):
        from_ts, to_ts = timestamps_from_dates("2024-01-01", "2024-01-02")
        assert from_ts == 1704067200
        assert to_ts == 1704153600
