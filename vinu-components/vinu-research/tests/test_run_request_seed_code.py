"""POST /research/run: a seed strategy must define the class the research loop runs (UserStrategy). A seed with another
class name used to be accepted and then died minutes later as an 'infrastructure failure' (simulator HTTP 422)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from vinu_research.server.routes_read import RunResearchRequest

BASE = {"symbol": "AAPL", "from_date": "2025-06-01", "to_date": "2026-09-30"}
GOOD = "class UserStrategy(BaseStrategy):\n    def generate_weights(self, data):\n        return data['close'] * 0\n"


def test_seed_defining_user_strategy_is_accepted():
    assert RunResearchRequest(**BASE, strategy_code=GOOD).strategy_code == GOOD


def test_no_seed_is_accepted():
    assert RunResearchRequest(**BASE).strategy_code is None


def test_seed_with_another_class_name_is_rejected_with_the_reason():
    with pytest.raises(ValidationError, match="must define a class named UserStrategy"):
        RunResearchRequest(**BASE, strategy_code=GOOD.replace("UserStrategy", "SmaCrossover"))


def test_seed_that_is_not_python_is_rejected():
    with pytest.raises(ValidationError, match="not valid Python"):
        RunResearchRequest(**BASE, strategy_code="class UserStrategy(:")
