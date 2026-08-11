import argparse
from unittest.mock import AsyncMock, patch

from vinu_live.cli import _parse_args, resolve_worker_interval, shadow_worker_main
from vinu_live.config import LiveConfig


class TestResolveWorkerInterval:
    def test_explicit_args_interval_wins(self) -> None:
        config = LiveConfig(worker_interval_sec=3600)
        args = argparse.Namespace(interval_sec=120)
        assert resolve_worker_interval(args, config) == 120

    def test_falls_back_to_config_when_args_interval_unset(self) -> None:
        config = LiveConfig(worker_interval_sec=3600)
        args = argparse.Namespace(interval_sec=None)
        assert resolve_worker_interval(args, config) == 3600

    def test_none_args_parses_sys_argv_directly(self) -> None:
        """Regression test for the console-script bug: `vinu-live-worker`
        (pyproject.toml's script entry) calls worker_main() with args=None,
        so a --interval flag on that command line has to be recovered from
        sys.argv, not silently ignored in favor of config/env defaults."""
        config = LiveConfig(worker_interval_sec=3600)
        with patch("sys.argv", ["vinu-live-worker", "--interval", "120"]):
            assert resolve_worker_interval(None, config) == 120

    def test_none_args_with_no_flag_falls_back_to_config(self) -> None:
        config = LiveConfig(worker_interval_sec=3600)
        with patch("sys.argv", ["vinu-live-worker"]):
            assert resolve_worker_interval(None, config) == 3600


class TestParseArgs:
    def test_worker_subcommand_interval_flag(self) -> None:
        args = _parse_args(["worker", "--interval", "90"])
        assert args.interval_sec == 90

    def test_shadow_worker_subcommand_interval_flag(self) -> None:
        args = _parse_args(["shadow-worker", "--interval", "45"])
        assert args.interval_sec == 45
        assert args.func is shadow_worker_main


class TestShadowWorkerMain:
    def test_calls_evaluate_all_and_stops_on_keyboard_interrupt(self) -> None:
        """Proves the wiring is real, not just parsed args: the worker
        loop actually calls ShadowEvaluator.evaluate_all() -- the
        mechanism Phase 4/5's own records flagged as correct-but-never-
        scheduled -- and exits cleanly on interrupt rather than hanging."""
        evaluate_calls = []

        async def _fake_evaluate_all():
            evaluate_calls.append(1)
            return [{"artifact_id": "a1", "promoted": True}, {"artifact_id": "a2", "promoted": False}]

        with patch("vinu_live.cli.load_config", return_value=LiveConfig(shadow_worker_interval_sec=1)), \
             patch("vinu_live.cli.ShadowEvaluator") as MockEvaluator, \
             patch("vinu_live.cli.time.sleep", side_effect=KeyboardInterrupt):
            instance = MockEvaluator.return_value
            instance.evaluate_all = _fake_evaluate_all
            instance.close = AsyncMock()

            shadow_worker_main(argparse.Namespace(interval_sec=None))

            assert evaluate_calls == [1]
            instance.close.assert_awaited_once()

    def test_explicit_interval_arg_overrides_config(self) -> None:
        with patch("vinu_live.cli.load_config", return_value=LiveConfig(shadow_worker_interval_sec=3600)), \
             patch("vinu_live.cli.ShadowEvaluator") as MockEvaluator, \
             patch("vinu_live.cli.time.sleep", side_effect=KeyboardInterrupt) as mock_sleep:
            instance = MockEvaluator.return_value

            async def _fake_evaluate_all():
                return []

            instance.evaluate_all = _fake_evaluate_all
            instance.close = AsyncMock()

            shadow_worker_main(argparse.Namespace(interval_sec=7))

            mock_sleep.assert_called_once_with(7)
