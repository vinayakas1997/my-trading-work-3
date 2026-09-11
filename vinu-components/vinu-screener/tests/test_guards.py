from __future__ import annotations

import math

from vinu_screener.conditions.guards import all_finite, is_finite_operand


class TestIsFiniteOperand:
    def test_normal_number_is_finite(self) -> None:
        assert is_finite_operand(1.5) is True
        assert is_finite_operand(0) is True
        assert is_finite_operand(-42) is True

    def test_none_is_not_finite(self) -> None:
        assert is_finite_operand(None) is False

    def test_inf_and_nan_are_not_finite(self) -> None:
        assert is_finite_operand(float("inf")) is False
        assert is_finite_operand(float("-inf")) is False
        assert is_finite_operand(float("nan")) is False
        assert is_finite_operand(math.nan) is False

    def test_the_bug_this_guards_against(self) -> None:
        # math.isnan(inf) is False -- so a naive `not math.isnan(v)` guard
        # would wrongly call inf "safe". is_finite_operand must not.
        assert not math.isnan(float("inf"))
        assert is_finite_operand(float("inf")) is False

    def test_non_numeric_string_is_not_finite(self) -> None:
        assert is_finite_operand("not a number") is False

    def test_numeric_string_is_finite(self) -> None:
        assert is_finite_operand("3.14") is True


class TestAllFinite:
    def test_all_finite_values(self) -> None:
        assert all_finite(1.0, 2.0, 3.0) is True

    def test_one_non_finite_fails_the_whole_check(self) -> None:
        assert all_finite(1.0, float("inf"), 3.0) is False

    def test_empty_is_vacuously_true(self) -> None:
        assert all_finite() is True
