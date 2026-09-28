"""Point 6's write-back path (missing-pieces-of-system/new-theory-of-
trading/system-wide-audit-and-design/reverse-engineering/
05-deciding-agent-and-precondition-tracking.md Part C): `tested`/
`precondition_held` now have a real writer -- overlaid onto the YAML-
sourced `precondition` dict at read time (StrategyAPI.get_strategy()),
never mutating the strategy's own file. Same
`_make_config`/YAML-file-on-disk pattern
test_live_decision_position_size.py already uses.
"""

from __future__ import annotations

from vinu_strategy.api import StrategyAPI
from vinu_strategy.config import VinuStrategyConfig
from vinu_strategy.storage.precondition_state import PreconditionStateStore


def _make_config(tmp_path, strategies_dir) -> VinuStrategyConfig:
    return VinuStrategyConfig(
        host="127.0.0.1", port=8084,
        data_root=tmp_path / "data", strategies_dir=strategies_dir,
        features_api_url="http://127.0.0.1:8082", correlation_api_url="http://127.0.0.1:8083",
        max_weight=0.25, cash_floor=0.10, rebalance_freq="daily",
        shared_watchlist_path=None,
    )


def _write_strategy(strategies_dir, name="sma_cross") -> None:
    strategies_dir.mkdir(exist_ok=True)
    (strategies_dir / f"{name}.yaml").write_text(
        f"name: {name}\n"
        "description: test\n"
        "schedule: 15m\n"
        "precondition:\n"
        "  description: market should be quiet before the cross\n"
        "  defined: true\n"
    )


class TestPreconditionStateStore:
    def test_unrecorded_strategy_returns_none(self, tmp_path) -> None:
        store = PreconditionStateStore(tmp_path / "precondition_state.db")
        assert store.get("sma_cross") is None

    def test_record_and_read_back(self, tmp_path) -> None:
        store = PreconditionStateStore(tmp_path / "precondition_state.db")
        store.record_check("sma_cross", precondition_held=True, checked_at="2026-09-28T12:00:00+00:00")
        state = store.get("sma_cross")
        assert state == {
            "tested": True, "precondition_held": True, "last_checked_at": "2026-09-28T12:00:00+00:00",
        }

    def test_precondition_held_none_round_trips_as_none_not_false(self, tmp_path) -> None:
        """A SKIP where the precondition genuinely didn't hold is
        `precondition_held=False`; an EXECUTE/SKIP where evidence was
        ambiguous either way can come back None -- must not collapse to
        False on the INTEGER<->bool conversion."""
        store = PreconditionStateStore(tmp_path / "precondition_state.db")
        store.record_check("sma_cross", precondition_held=None, checked_at="2026-09-28T12:00:00+00:00")
        state = store.get("sma_cross")
        assert state["tested"] is True
        assert state["precondition_held"] is None

    def test_recording_again_overwrites_not_appends(self, tmp_path) -> None:
        store = PreconditionStateStore(tmp_path / "precondition_state.db")
        store.record_check("sma_cross", precondition_held=False, checked_at="2026-09-28T12:00:00+00:00")
        store.record_check("sma_cross", precondition_held=True, checked_at="2026-09-28T13:00:00+00:00")
        state = store.get("sma_cross")
        assert state["precondition_held"] is True
        assert state["last_checked_at"] == "2026-09-28T13:00:00+00:00"

    def test_strategies_are_independent(self, tmp_path) -> None:
        store = PreconditionStateStore(tmp_path / "precondition_state.db")
        store.record_check("sma_cross", precondition_held=True, checked_at="2026-09-28T12:00:00+00:00")
        assert store.get("rsi_reversal") is None


class TestStrategyAPIOverlaysPreconditionState:
    def test_no_check_recorded_yet_defaults_to_tested_false(self, tmp_path) -> None:
        strategies_dir = tmp_path / "strategies"
        _write_strategy(strategies_dir)
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        result = api.get_strategy("sma_cross")

        assert result["precondition"]["defined"] is True
        assert result["precondition"]["tested"] is False
        assert result["precondition"]["precondition_held"] is None
        assert result["precondition"]["description"] == "market should be quiet before the cross"

    def test_recording_a_check_flips_tested_and_is_visible_on_next_read(self, tmp_path) -> None:
        strategies_dir = tmp_path / "strategies"
        _write_strategy(strategies_dir)
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        response = api.record_precondition_check("sma_cross", precondition_held=True)
        assert response["precondition"]["tested"] is True
        assert response["precondition"]["precondition_held"] is True

        result = api.get_strategy("sma_cross")
        assert result["precondition"]["tested"] is True
        assert result["precondition"]["precondition_held"] is True
        # The human-authored description survives the overlay unchanged.
        assert result["precondition"]["description"] == "market should be quiet before the cross"

    def test_a_skip_still_counts_as_tested(self, tmp_path) -> None:
        """Being checked and failing is still being tested -- SKIP
        (precondition_held=False) must flip `tested`, not just EXECUTE."""
        strategies_dir = tmp_path / "strategies"
        _write_strategy(strategies_dir)
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        api.record_precondition_check("sma_cross", precondition_held=False)

        result = api.get_strategy("sma_cross")
        assert result["precondition"]["tested"] is True
        assert result["precondition"]["precondition_held"] is False

    def test_recording_for_an_unknown_strategy_is_a_404(self, tmp_path) -> None:
        import pytest
        from fastapi import HTTPException

        strategies_dir = tmp_path / "strategies"
        strategies_dir.mkdir()
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        with pytest.raises(HTTPException) as exc_info:
            api.record_precondition_check("ghost", precondition_held=True)
        assert exc_info.value.status_code == 404

    def test_the_yaml_file_itself_is_never_modified(self, tmp_path) -> None:
        strategies_dir = tmp_path / "strategies"
        _write_strategy(strategies_dir)
        yaml_path = strategies_dir / "sma_cross.yaml"
        original_contents = yaml_path.read_text()
        api = StrategyAPI(_make_config(tmp_path, strategies_dir))

        api.record_precondition_check("sma_cross", precondition_held=True)

        assert yaml_path.read_text() == original_contents
