from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from vinu_agent.tools.factor_backtest_tool import FactorBacktestTool


def _tool() -> FactorBacktestTool:
    tool = FactorBacktestTool()
    tool._services_config = {"vinu_stock_price": "http://vinu-stock-price:8081"}
    return tool


def _candle_rows(n: int, base_price: float, seed_offset: int) -> list[dict]:
    import random

    rng = random.Random(seed_offset)
    rows = []
    price = base_price
    start_ts = 1700000000
    for i in range(n):
        price += rng.uniform(-1.0, 1.0)
        ts = start_ts + i * 86400
        rows.append({
            "symbol": "X",
            "provider": "test",
            "bar_ts": ts,
            "open": price - 0.1,
            "high": price + 0.5,
            "low": price - 0.5,
            "close": price,
            "volume": 1_000_000 + i * 1000,
            "vwap": price,
            "trades": 100,
            "adj_factor": 1.0,
        })
    return rows


class TestFactorBacktestToolSynthetic:
    def test_no_symbols_uses_synthetic_and_labels_it(self) -> None:
        result = json.loads(_tool().execute(factor="alpha101_001"))
        assert result["status"] == "ok"
        assert result["data_source"] == "synthetic"
        assert "note" in result
        assert "metrics" in result

    def test_synthetic_never_calls_stock_price_api(self) -> None:
        with patch("httpx.Client") as mock_client:
            _tool().execute(factor="alpha101_001")
        mock_client.assert_not_called()


class TestFactorBacktestToolRealData:
    def test_symbols_fetches_real_data_and_labels_it(self) -> None:
        rows_a = _candle_rows(60, 100.0, 1)
        rows_b = _candle_rows(60, 50.0, 2)

        mock_resp_a = MagicMock()
        mock_resp_a.raise_for_status.return_value = None
        mock_resp_a.json.return_value = {"count": len(rows_a), "data": rows_a}
        mock_resp_b = MagicMock()
        mock_resp_b.raise_for_status.return_value = None
        mock_resp_b.json.return_value = {"count": len(rows_b), "data": rows_b}

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = [mock_resp_a, mock_resp_b]

        with patch("httpx.Client", return_value=mock_client):
            result = json.loads(_tool().execute(factor="alpha101_001", symbols="AAA,BBB"))

        assert result["status"] == "ok"
        assert result["data_source"] == "real"
        assert result["symbols_used"] == ["AAA", "BBB"]
        assert result["symbols_failed"] == []
        assert "metrics" in result

    def test_partial_symbol_failure_reports_failed_list(self) -> None:
        rows_a = _candle_rows(60, 100.0, 1)
        rows_b = _candle_rows(60, 50.0, 2)

        mock_resp_a = MagicMock()
        mock_resp_a.raise_for_status.return_value = None
        mock_resp_a.json.return_value = {"count": len(rows_a), "data": rows_a}
        mock_resp_b = MagicMock()
        mock_resp_b.raise_for_status.return_value = None
        mock_resp_b.json.return_value = {"count": len(rows_b), "data": rows_b}
        mock_resp_c = MagicMock()
        mock_resp_c.raise_for_status.side_effect = RuntimeError("404 not found")

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = [mock_resp_a, mock_resp_b, mock_resp_c]

        with patch("httpx.Client", return_value=mock_client):
            result = json.loads(_tool().execute(factor="alpha101_001", symbols="AAA,BBB,CCC"))

        assert result["status"] == "ok"
        assert result["data_source"] == "real"
        assert result["symbols_used"] == ["AAA", "BBB"]
        assert len(result["symbols_failed"]) == 1
        assert result["symbols_failed"][0]["symbol"] == "CCC"

    def test_all_symbols_fail_returns_error_not_synthetic_fallback(self) -> None:
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = RuntimeError("down")

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client", return_value=mock_client):
            result = json.loads(_tool().execute(factor="alpha101_001", symbols="AAA,BBB"))

        assert result["status"] == "error"
        assert "data_source" not in result
        assert len(result["symbols_failed"]) == 2

    def test_single_working_symbol_is_not_enough(self) -> None:
        rows_a = _candle_rows(60, 100.0, 1)
        mock_resp_a = MagicMock()
        mock_resp_a.raise_for_status.return_value = None
        mock_resp_a.json.return_value = {"count": len(rows_a), "data": rows_a}
        mock_resp_b = MagicMock()
        mock_resp_b.raise_for_status.side_effect = RuntimeError("down")

        mock_client = MagicMock()
        mock_client.__enter__.return_value = mock_client
        mock_client.get.side_effect = [mock_resp_a, mock_resp_b]

        with patch("httpx.Client", return_value=mock_client):
            result = json.loads(_tool().execute(factor="alpha101_001", symbols="AAA,BBB"))

        assert result["status"] == "error"
        assert "data_source" not in result
