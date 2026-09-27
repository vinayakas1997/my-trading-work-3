from __future__ import annotations

from vinu_infra.point_in_time import clamp_to_as_of


class TestClampToAsOf:
    """item #21 pattern #1: the shared server-side as-of enforcement
    function, built once so vinu-stock-price and vinu-news don't each
    reinvent (or forget) the same clamp."""

    def test_no_as_of_set_returns_value_unchanged_and_not_clamped(self) -> None:
        assert clamp_to_as_of(2000, None) == (2000, False)

    def test_no_as_of_set_and_no_value_stays_none(self) -> None:
        """Live (non-replay) use with no explicit end at all -- nothing to
        clamp against, so no default is substituted here."""
        assert clamp_to_as_of(None, None) == (None, False)

    def test_value_beyond_as_of_is_clamped(self) -> None:
        assert clamp_to_as_of(2000, 1000) == (1000, True)

    def test_value_within_as_of_is_not_clamped(self) -> None:
        assert clamp_to_as_of(500, 1000) == (500, False)

    def test_value_exactly_at_as_of_is_not_clamped(self) -> None:
        assert clamp_to_as_of(1000, 1000) == (1000, False)

    def test_missing_value_with_as_of_set_defaults_to_as_of_and_reports_clamped(self) -> None:
        """The actual gap this closes: an unbounded query (no end
        requested at all) under a replay as_of must not slip through as
        "no clamp needed" just because there was nothing to compare
        against -- it becomes bounded at as_of, and that's still a real
        clamp (the effective range changed)."""
        assert clamp_to_as_of(None, 1000) == (1000, True)
