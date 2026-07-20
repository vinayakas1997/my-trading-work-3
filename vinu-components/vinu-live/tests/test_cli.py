import argparse
from unittest.mock import patch

from vinu_live.cli import _parse_args, resolve_worker_interval
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
