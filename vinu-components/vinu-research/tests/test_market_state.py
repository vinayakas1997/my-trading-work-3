from __future__ import annotations

from vinu_research.market_state import MarketState


class TestMarketState:
    def test_from_parts_matches_trade_plan_tool_kwarg_names(self) -> None:
        # trade_plan_tool.py's _build_structured_plan/_render_plan already use
        # these exact keyword names for their dict args (angles, features,
        # liquidity, news, validation, ...) -- MarketState.from_parts must
        # accept them unchanged so the migration in trade_plan_tool.py stays
        # additive, not a rename.
        state = MarketState.from_parts(
            "AAPL",
            angles={"trend_lifecycle": [{"stage": "strong"}]},
            features={"rsi_14": 55.0},
            liquidity={"normal": True},
            news={"status": "available"},
            validation={"status": "available"},
            active_strategies=[{"artifact_id": "art_1"}],
        )
        assert state.symbol == "AAPL"
        assert state.angles["trend_lifecycle"][0]["stage"] == "strong"
        assert state.features["rsi_14"] == 55.0
        assert state.liquidity == {"normal": True}
        assert state.news == {"status": "available"}
        assert state.validation == {"status": "available"}
        assert state.active_strategies == [{"artifact_id": "art_1"}]
        # Phase 4/5 fields default empty until those phases wire them up.
        assert state.options == {}
        assert state.market_regime_stats == {}

    def test_from_parts_ignores_unknown_keys(self) -> None:
        state = MarketState.from_parts("AAPL", angles={}, bogus_kwarg=123)
        assert state.symbol == "AAPL"
        assert not hasattr(state, "bogus_kwarg")

    def test_to_dict_round_trips_all_fields(self) -> None:
        state = MarketState(symbol="AAPL", as_of="2024-01-01", risk_state={"status": "ok"})
        d = state.to_dict()
        assert d["symbol"] == "AAPL"
        assert d["as_of"] == "2024-01-01"
        assert d["risk_state"] == {"status": "ok"}
        for key in (
            "angles", "features", "liquidity", "news", "options",
            "risk_state", "validation", "active_strategies", "market_regime_stats",
        ):
            assert key in d
