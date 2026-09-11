from __future__ import annotations

import pytest

from vinu_screener.conditions.schema import parse_condition
from vinu_screener.rules.actions import ActionsConfig
from vinu_screener.rules.store import RuleStore
from vinu_screener.scan.monitor import ScanRule
from vinu_screener.scan.universe import CoarseFilter


@pytest.fixture
def store():
    return RuleStore(":memory:")


def _rule(rule_id="r1", **overrides) -> ScanRule:
    defaults = dict(
        rule_id=rule_id,
        condition=parse_condition({"indicator": "close", "operator": ">", "value": 100.0}),
        universe=("AAPL", "MSFT"),
    )
    defaults.update(overrides)
    return ScanRule(**defaults)


class TestRoundTrip:
    def test_upsert_then_get_reconstructs_an_equivalent_rule(self, store) -> None:
        rule = _rule(cooldown_min=15.0, coarse_filter=CoarseFilter(min_price=5.0))
        store.upsert_rule(rule, interval_sec=90.0)
        stored = store.get("r1")
        assert stored is not None
        assert stored.rule.rule_id == "r1"
        assert stored.rule.universe == ("AAPL", "MSFT")
        assert stored.rule.cooldown_min == 15.0
        assert stored.rule.coarse_filter.min_price == 5.0
        assert stored.interval_sec == 90.0
        assert stored.active is True

    def test_round_trips_actions_and_mode(self, store) -> None:
        rule = _rule(actions=ActionsConfig(toast=False, providers={"telegram": True}), mode="one_shot")
        store.upsert_rule(rule)
        stored = store.get("r1")
        assert stored.rule.mode == "one_shot"
        assert stored.rule.actions.providers == {"telegram": True}

    def test_get_unknown_rule_is_none(self, store) -> None:
        assert store.get("ghost") is None


class TestUpsertSemantics:
    def test_second_upsert_replaces_and_preserves_created_at(self, store) -> None:
        store.upsert_rule(_rule(cooldown_min=1.0), interval_sec=60.0)
        first = store.get("r1")
        store.upsert_rule(_rule(cooldown_min=2.0), interval_sec=120.0)
        second = store.get("r1")
        assert second.rule.cooldown_min == 2.0
        assert second.interval_sec == 120.0
        assert second.created_at == first.created_at
        assert second.updated_at >= first.updated_at


class TestIntervalFloor:
    def test_interval_below_the_rate_limit_floor_is_raised(self, store) -> None:
        stored = store.upsert_rule(_rule(), interval_sec=1.0)
        from vinu_screener.scan.monitor import MIN_INTERVAL_SEC

        assert stored.interval_sec == MIN_INTERVAL_SEC

    def test_interval_above_the_floor_is_respected(self, store) -> None:
        stored = store.upsert_rule(_rule(), interval_sec=120.0)
        assert stored.interval_sec == 120.0


class TestListingAndActivation:
    def test_all_lists_every_rule(self, store) -> None:
        store.upsert_rule(_rule("r1"))
        store.upsert_rule(_rule("r2"))
        assert {s.rule.rule_id for s in store.all()} == {"r1", "r2"}

    def test_active_only_excludes_disabled_rules(self, store) -> None:
        store.upsert_rule(_rule("r1"), active=True)
        store.upsert_rule(_rule("r2"), active=False)
        assert [s.rule.rule_id for s in store.all(active_only=True)] == ["r1"]

    def test_set_active_toggles_a_rule(self, store) -> None:
        store.upsert_rule(_rule("r1"), active=True)
        assert store.set_active("r1", False) is True
        assert store.get("r1").active is False

    def test_set_active_on_unknown_rule_returns_false(self, store) -> None:
        assert store.set_active("ghost", False) is False


class TestDelete:
    def test_delete_removes_the_rule(self, store) -> None:
        store.upsert_rule(_rule("r1"))
        assert store.delete("r1") is True
        assert store.get("r1") is None

    def test_delete_unknown_rule_returns_false(self, store) -> None:
        assert store.delete("ghost") is False

    def test_delete_is_independent_per_rule(self, store) -> None:
        store.upsert_rule(_rule("r1"))
        store.upsert_rule(_rule("r2"))
        store.delete("r1")
        assert store.get("r2") is not None
