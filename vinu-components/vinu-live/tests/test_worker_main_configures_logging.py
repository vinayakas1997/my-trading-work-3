"""The hourly order scheduler must not run silent. `vinu-live-worker` calls
worker_main directly (bypassing main()), so worker_main has to configure
logging itself, or its cycle-complete and failure lines are never emitted."""
from __future__ import annotations

import pytest

from vinu_live import cli


def test_worker_main_configures_logging_before_it_does_anything_else(monkeypatch):
    calls: list[str] = []
    monkeypatch.setattr(cli, "setup_logging", lambda name: calls.append(f"logging:{name}"))

    def _stop(*_a, **_k):
        calls.append("config")
        raise RuntimeError("stop after logging is set")

    monkeypatch.setattr(cli, "load_config", _stop)
    with pytest.raises(RuntimeError, match="stop after logging"):
        cli.worker_main(None)
    assert calls == ["logging:live", "config"]
