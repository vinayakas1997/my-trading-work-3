"""With the models container dormant the FinBERT worker finishes cleanly instead of crashing on an unreachable service.

It used to raise `ModelServiceError` at every start; unnoticed while background workers were unsupervised, and an endless
restart loop with a traceback every few minutes once they were."""

from __future__ import annotations

import pytest

from vinu_news import cli


def test_the_worker_exits_cleanly_when_models_are_disabled(monkeypatch):
    monkeypatch.setenv("VINU_MODELS_ENABLED", "false")
    import vinu_infra.model_policy as policy

    monkeypatch.setattr(policy, "MODELS_ENABLED", False, raising=False)

    class Boom:
        def __init__(self, *a, **k):
            raise AssertionError("the service must not be opened when models are disabled")

    monkeypatch.setattr(cli, "NewsService", Boom)
    assert cli.finbert_main([]) is None


def test_the_worker_still_runs_a_sweep_when_models_are_enabled(monkeypatch):
    import vinu_infra.model_policy as policy

    monkeypatch.setattr(policy, "MODELS_ENABLED", True, raising=False)
    monkeypatch.setenv("VINU_MODELS_ENABLED", "true")
    calls = []

    class Svc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def backfill_finbert_sentiment(self, limit=500):
            calls.append(limit)
            return {"scored": 0, "remaining": 0}

    monkeypatch.setattr(cli, "NewsService", Svc)
    cli.finbert_main(["--once"])
    assert calls == [500]
