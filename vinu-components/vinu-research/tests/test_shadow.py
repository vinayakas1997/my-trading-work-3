from __future__ import annotations

import tempfile
import pytest
from pathlib import Path

from vinu_research.shadow.attribution import decompose_pnl
from vinu_research.shadow.backtester import (
    prepare_backtest_config,
    select_liquid_baskets,
)
from vinu_research.shadow.codegen import generate_signal_engine, validate_generated_code
from vinu_research.shadow.extractor import _pair_trades_fifo, extract_profile
from vinu_research.shadow.models import ShadowProfile, ShadowRule
from vinu_research.shadow.reporter import generate_html_report
from vinu_research.shadow.storage import ShadowStorage


class TestShadowModels:
    def test_shadow_rule_roundtrip(self):
        rule = ShadowRule(
            rule_id="r1",
            human_text="Hold 5-10 days",
            entry_condition={"holding_days_min": 5},
            exit_condition={"holding_days_max": 10},
            holding_days_range=(5.0, 10.0),
            weight=0.8,
        )
        d = rule.to_dict()
        restored = ShadowRule.from_dict(d)
        assert restored.rule_id == "r1"
        assert restored.holding_days_range == (5.0, 10.0)

    def test_shadow_profile_roundtrip(self):
        rule = ShadowRule(rule_id="r1", human_text="Test rule")
        profile = ShadowProfile(
            shadow_id="sh_test",
            journal_hash="abc123",
            rules=[rule],
            preferred_markets=["AAPL"],
        )
        d = profile.to_dict()
        restored = ShadowProfile.from_dict(d)
        assert restored.shadow_id == "sh_test"
        assert len(restored.rules) == 1


class TestShadowExtractor:
    def test_pair_trades_fifo(self):
        rows = [
            {"date": "2024-01-01", "symbol": "AAPL", "side": "BUY", "price": 150.0, "shares": 10},
            {"date": "2024-01-10", "symbol": "AAPL", "side": "SELL", "price": 160.0, "shares": 10},
        ]
        roundtrips = _pair_trades_fifo(rows)
        assert len(roundtrips) == 1
        assert roundtrips[0]["pnl"] == 100.0
        assert roundtrips[0]["holding_days"] == 9

    def test_fifo_multiple_buys(self):
        rows = [
            {"date": "2024-01-01", "symbol": "AAPL", "side": "BUY", "price": 100.0, "shares": 10},
            {"date": "2024-01-05", "symbol": "AAPL", "side": "BUY", "price": 110.0, "shares": 5},
            {"date": "2024-01-10", "symbol": "AAPL", "side": "SELL", "price": 120.0, "shares": 8},
            {"date": "2024-01-15", "symbol": "AAPL", "side": "SELL", "price": 130.0, "shares": 7},
        ]
        roundtrips = _pair_trades_fifo(rows)
        assert len(roundtrips) == 3

    def test_fifo_short_trades(self):
        rows = [
            {"date": "2024-01-01", "symbol": "AAPL", "side": "SELL", "price": 100.0, "shares": 10},
            {"date": "2024-01-10", "symbol": "AAPL", "side": "BUY", "price": 90.0, "shares": 10},
        ]
        roundtrips = _pair_trades_fifo(rows)
        assert len(roundtrips) == 1
        assert roundtrips[0]["pnl"] == 100.0
        assert roundtrips[0]["pnl_pct"] == pytest.approx(0.11111, rel=1e-4)

    def test_extract_profile_creates_shadow(self):
        rows = [
            {"date": "2024-01-01", "symbol": "AAPL", "side": "BUY", "price": 150.0, "shares": 10},
            {"date": "2024-01-10", "symbol": "AAPL", "side": "SELL", "price": 160.0, "shares": 10},
            {"date": "2024-02-01", "symbol": "MSFT", "side": "BUY", "price": 300.0, "shares": 5},
            {"date": "2024-02-15", "symbol": "MSFT", "side": "SELL", "price": 320.0, "shares": 5},
            {"date": "2024-03-01", "symbol": "GOOGL", "side": "BUY", "price": 140.0, "shares": 20},
            {"date": "2024-03-10", "symbol": "GOOGL", "side": "SELL", "price": 145.0, "shares": 20},
        ]
        profile = extract_profile(rows)
        assert profile.shadow_id.startswith("sh_")
        assert profile.journal_entries == 6
        assert profile.profitable_roundtrips == 3


class TestShadowCodegen:
    def test_generates_valid_code(self):
        profile = ShadowProfile(
            shadow_id="sh_test",
            journal_hash="abc",
            rules=[
                ShadowRule(rule_id="r1", human_text="Hold 5-10 days in AAPL",
                           entry_condition={"holding_days_min": 5, "holding_days_max": 10}),
            ],
        )
        code = generate_signal_engine(profile)
        assert "class SignalEngine" in code
        assert "compute_signals" in code
        assert validate_generated_code(code)

    def test_rejects_dangerous_code(self):
        assert not validate_generated_code('import os; os.system("rm -rf /")')
        assert not validate_generated_code('eval("1+1")')


class TestShadowBacktester:
    def test_select_liquid_baskets(self):
        profile = ShadowProfile(
            shadow_id="sh_test",
            journal_hash="abc",
            preferred_markets=["AAPL", "MSFT", "GOOGL", "AAPL"],
        )
        symbols = select_liquid_baskets(profile)
        assert symbols == ["AAPL", "MSFT", "GOOGL"]
        assert len(symbols) == 3

    def test_prepare_backtest_config(self):
        profile = ShadowProfile(
            shadow_id="sh_test",
            journal_hash="abc",
            preferred_markets=["AAPL"],
            rules=[ShadowRule(rule_id="r1", human_text="Test")],
        )
        tmp = tempfile.mkdtemp()
        config_path = prepare_backtest_config(profile, "2024-01-01", "2024-12-31", tmp)
        assert Path(config_path).exists()


class TestShadowAttribution:
    def test_decompose_pnl(self):
        trades = [
            {"pnl": 100.0, "holding_days": 5},
            {"pnl": 50.0, "holding_days": 7},
            {"pnl": -20.0, "holding_days": 3},
            {"pnl": 30.0, "holding_days": 10},
            {"pnl": 10.0, "holding_days": 6},
        ]
        result = decompose_pnl(trades)
        assert "total_pnl" in result
        assert result["total_pnl"] == 170.0

    def test_empty_trades(self):
        result = decompose_pnl([])
        assert result["total_pnl"] == 0.0


class TestShadowReporter:
    def test_generates_html(self):
        profile = ShadowProfile(
            shadow_id="sh_test",
            journal_hash="abc",
            profile_text="Test profile",
            rules=[ShadowRule(rule_id="r1", human_text="Hold 5 days")],
            journal_entries=10,
            profitable_roundtrips=5,
        )
        html = generate_html_report(profile, attribution={"total_pnl": 100.0})
        assert "<html>" in html
        assert "sh_test" in html
        assert "Hold 5 days" in html


class TestShadowStorage:
    def test_save_and_load(self):
        tmp = Path(tempfile.mkdtemp())
        store = ShadowStorage(tmp)
        profile = ShadowProfile(
            shadow_id="sh_test",
            journal_hash="abc123",
            profile_text="Test",
        )
        store.save(profile)
        loaded = store.load("sh_test")
        assert loaded is not None
        assert loaded.shadow_id == "sh_test"

    def test_idempotent_by_hash(self):
        tmp = Path(tempfile.mkdtemp())
        store = ShadowStorage(tmp)
        rows = [{"date": "2024-01-01", "symbol": "AAPL", "side": "BUY", "price": 150.0, "shares": 10}]
        jh = ShadowStorage.compute_hash(rows)
        assert len(jh) == 40
        assert store.exists(jh) is None

    def test_list_all(self):
        tmp = Path(tempfile.mkdtemp())
        store = ShadowStorage(tmp)
        store.save(ShadowProfile(shadow_id="sh_a", journal_hash="a"))
        store.save(ShadowProfile(shadow_id="sh_b", journal_hash="b"))
        profiles = store.list_all()
        assert len(profiles) == 2

    def test_delete(self):
        tmp = Path(tempfile.mkdtemp())
        store = ShadowStorage(tmp)
        store.save(ShadowProfile(shadow_id="sh_del", journal_hash="del"))
        assert store.delete("sh_del") is True
        assert store.delete("sh_del") is False
