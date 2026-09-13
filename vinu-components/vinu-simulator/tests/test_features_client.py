from __future__ import annotations

import logging

import pytest

from vinu_simulator.clients.features_client import FeaturesClient


class TestGetIndicatorsFailureIsLogged:
    """
    #32: get_indicators used to swallow any fetch exception and return None
    with zero logging of its own -- a silent drop that, composed with #31's
    generate_weights crash-fallback, made a missing-indicator-driven crash
    indistinguishable from "no indicators were ever requested". It must now
    log the failure clearly.
    """

    def test_fetch_exception_is_logged_and_returns_none(self, caplog):
        client = FeaturesClient(base_url="http://features.invalid")

        def _boom(path, params=None):
            raise RuntimeError("connection refused")

        client.get = _boom

        with caplog.at_level(logging.WARNING, logger="vinu_simulator.clients.features_client"):
            result = client.get_indicators("AAPL", ["rsi_14"], 0, 100)

        assert result is None
        assert any(
            "AAPL" in rec.message and "rsi_14" in rec.message
            for rec in caplog.records
        )

    def test_successful_fetch_is_unaffected(self):
        client = FeaturesClient(base_url="http://features.invalid")
        client.get = lambda path, params=None: [
            {"ts": 0, "rsi_14": 55.0},
            {"ts": 86400, "rsi_14": 60.0},
        ]

        result = client.get_indicators("AAPL", ["rsi_14"], 0, 100)

        assert result is not None
        assert "rsi_14" in result.columns
        assert len(result) == 2
