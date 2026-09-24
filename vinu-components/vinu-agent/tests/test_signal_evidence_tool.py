import json
from unittest.mock import MagicMock, patch

import pytest

from vinu_agent.tools.signal_evidence_tool import GetSignalEvidenceTool
from vinu_research.storage.signal_evidence_store import SignalEvidenceStore


def _tool(services_config: dict | None = None) -> GetSignalEvidenceTool:
    tool = GetSignalEvidenceTool()
    tool._services_config = services_config or {}
    return tool


def _force_in_process_unavailable():
    return patch(
        "vinu_agent.broker.research_link.get_signal_evidence_store",
        side_effect=RuntimeError("not available"),
    )


@pytest.fixture
def store(tmp_path) -> SignalEvidenceStore:
    s = SignalEvidenceStore(tmp_path / "signal_evidence.db")
    yield s
    s.close()


class TestGetSignalEvidenceToolInProcess:
    def test_lists_real_triggers_for_a_symbol(self, store) -> None:
        store.record_trigger(
            "AAPL-sma5_cross_sma50-1", "AAPL", "2025-03-11T14:30:00Z",
            "sma5_cross_sma50", {"adx": 17.8, "rsi": 55.0},
        )
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_signal_evidence_store", return_value=store):
            result = json.loads(tool.execute(symbol="aapl"))
        assert result["status"] == "ok"
        assert result["symbol"] == "AAPL"
        assert result["count"] == 1
        assert result["outcomes_recorded"] == 0
        assert result["triggers"][0]["trigger_id"] == "AAPL-sma5_cross_sma50-1"
        # list_triggers is metadata-only (per SignalEvidenceStore's own
        # docstring) -- no indicator payload in the summary list.
        assert "indicators" not in result["triggers"][0]

    def test_outcomes_recorded_counts_only_resolved_triggers(self, store) -> None:
        store.record_trigger("t-1", "AAPL", "2025-03-11T14:30:00Z", "sma5_cross_sma50", {"adx": 17.8})
        store.record_trigger("t-2", "AAPL", "2025-03-12T09:45:00Z", "sma5_cross_sma50", {"adx": 9.2})
        store.record_outcome(
            "t-1", max_favorable_excursion=0.03, max_adverse_excursion=-0.01, return_at_horizon=0.024,
        )
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_signal_evidence_store", return_value=store):
            result = json.loads(tool.execute(symbol="AAPL"))
        assert result["count"] == 2
        assert result["outcomes_recorded"] == 1

    def test_unknown_symbol_returns_empty_not_error(self, store) -> None:
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_signal_evidence_store", return_value=store):
            result = json.loads(tool.execute(symbol="ZZZZ"))
        assert result["status"] == "ok"
        assert result["count"] == 0
        assert result["triggers"] == []

    def test_trigger_id_fetches_full_indicator_snapshot(self, store) -> None:
        store.record_trigger(
            "t-1", "AAPL", "2025-03-11T14:30:00Z", "sma5_cross_sma50",
            {"adx": 17.8, "sma_5": 101.2},
        )
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_signal_evidence_store", return_value=store):
            result = json.loads(tool.execute(trigger_id="t-1"))
        assert result["status"] == "ok"
        assert result["trigger"]["indicators"] == {"adx": 17.8, "sma_5": 101.2}

    def test_unknown_trigger_id_returns_not_found(self, store) -> None:
        tool = _tool()
        with patch("vinu_agent.broker.research_link.get_signal_evidence_store", return_value=store):
            result = json.loads(tool.execute(trigger_id="does-not-exist"))
        assert result["status"] == "not_found"
        assert result["trigger_id"] == "does-not-exist"

    def test_falls_back_to_http_when_in_process_raises(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"triggers": [], "count": 0}
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = json.loads(tool.execute(symbol="AAPL"))
        mock_get.assert_called_once()
        assert result == {"status": "ok", "symbol": "AAPL", "count": 0, "outcomes_recorded": 0, "triggers": []}


class TestGetSignalEvidenceToolHttpFallback:
    def test_uses_configured_service_url_and_prefix(self) -> None:
        tool = _tool({"vinu_research": "http://research-api:8087"})
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"triggers": [], "count": 0}
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute(symbol="AAPL")
        args, kwargs = mock_get.call_args
        assert args[0] == "http://research-api:8087/research/signal-evidence"
        assert kwargs["params"] == {"limit": 50, "symbol": "AAPL"}

    def test_falls_back_to_default_url(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"triggers": [], "count": 0}
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            tool.execute()
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/signal-evidence"

    def test_trigger_id_hits_the_single_trigger_route(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"trigger_id": "t-1", "indicators": {"adx": 17.8}}
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp) as mock_get:
            result = json.loads(tool.execute(trigger_id="t-1"))
        args, _ = mock_get.call_args
        assert args[0] == "http://localhost:8087/research/signal-evidence/t-1"
        assert result == {"status": "ok", "trigger": {"trigger_id": "t-1", "indicators": {"adx": 17.8}}}

    def test_trigger_id_404_returns_not_found(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            result = json.loads(tool.execute(trigger_id="missing"))
        assert result == {"status": "not_found", "trigger_id": "missing"}

    def test_raises_on_http_error(self) -> None:
        tool = _tool()
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("boom")
        with _force_in_process_unavailable(), patch("httpx.get", return_value=mock_resp):
            with pytest.raises(RuntimeError):
                tool.execute()
