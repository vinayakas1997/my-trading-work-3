"""situation-test/19-corrupted-mandate-loosens-ticker-allowlist.md: a
mandate.yaml that fails to PARSE (as opposed to one that simply doesn't
exist yet) must not silently fall back to the maximally permissive
allowed_tickers default -- an operator's real, deliberately-configured
ticker restriction would otherwise be discarded with only a log line to
notice it by. See broker/mandate.py's TradingMandate.load().
"""

from __future__ import annotations

from pathlib import Path

from vinu_agent.broker.mandate import TradingMandate


class TestMissingMandateFileUsesPermissiveDefaults:
    """The genuinely-no-configuration-yet case is unaffected by this fix --
    still falls back to allowed_tickers={"*"}."""

    def test_no_file_at_all_defaults_to_allow_all(self, tmp_path: Path) -> None:
        mandate = TradingMandate.load(tmp_path / "does-not-exist.yaml")

        assert mandate.allowed_tickers == {"*"}


class TestCorruptedMandateFileFailsClosed:
    def test_unparseable_yaml_blocks_every_ticker_instead_of_allowing_all(self, tmp_path: Path) -> None:
        path = tmp_path / "mandate.yaml"
        path.write_text('allowed_tickers: ["AAPL", "MSFT"\nthis is not valid yaml: [[[\n')

        mandate = TradingMandate.load(path)

        assert mandate.allowed_tickers == set()
        assert "*" not in mandate.allowed_tickers

    def test_a_real_operator_restriction_is_not_silently_widened_by_corruption(self, tmp_path: Path) -> None:
        """The regression this guards against: a real, working config that
        restricts trading to two tickers, then gets corrupted (e.g. a bad
        manual edit) -- the fallback must not revert to allowing everything."""
        path = tmp_path / "mandate.yaml"
        path.write_text("allowed_tickers: [\"AAPL\", \"MSFT\"]\nmax_order_value: 1000.0\n")
        good = TradingMandate.load(path)
        assert good.allowed_tickers == {"AAPL", "MSFT"}

        path.write_text('allowed_tickers: ["AAPL", "MSFT"\nbroken: [[[\n')
        corrupted = TradingMandate.load(path)

        assert "*" not in corrupted.allowed_tickers
        assert corrupted.allowed_tickers != good.allowed_tickers  # narrower, never wider

    def test_reduce_only_still_works_under_the_fail_closed_fallback(self, tmp_path: Path) -> None:
        """The fail-closed fallback must not trap an existing position --
        order_guard.py's allowed_tickers check exempts reduce_only
        (situation 22), so this fallback's empty allowlist still lets an
        exit through even though it blocks every new/increasing order.
        Every other mandate switch is neutralized here (require_active_artifact
        etc.) so this test isolates the allowed_tickers interaction
        specifically -- those other checks have their own coverage
        elsewhere (situation 22, TestRequireActiveArtifact, ...)."""
        from unittest.mock import MagicMock

        from vinu_agent.broker.daily_limits import DailyLimitStore
        from vinu_agent.broker.order_guard import OrderGuard

        path = tmp_path / "mandate.yaml"
        path.write_text("not: valid: yaml: [[[\n")
        fallback = TradingMandate.load(path)
        assert fallback.allowed_tickers == set()

        mandate = TradingMandate(
            allowed_tickers=fallback.allowed_tickers,
            require_active_artifact=False, require_market_open=False,
            max_position_pct=1.0, max_capital_utilization_pct=1.0,
        )
        broker = MagicMock()
        broker.get_account.return_value = MagicMock(equity=100_000.0, cash=100_000.0)
        guard = OrderGuard(
            mandate=mandate, broker=broker,
            daily_limit_store=DailyLimitStore(tmp_path / "daily_limits.db"),
        )

        new_buy = guard.check("AAPL", "buy", qty=1, price=100.0)
        reduce_only_sell = guard.check("AAPL", "sell", qty=1, price=100.0, reduce_only=True)

        assert not new_buy
        assert reduce_only_sell
