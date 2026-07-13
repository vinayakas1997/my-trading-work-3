"""Provider registry tests with mocked HTTP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from vinu_stock.providers.registry import ProviderRegistry
from vinu_stock.providers.yahoo import YahooProvider, _parse_yahoo_chart
from vinu_stock.storage.models import BarRecord


def test_parse_yahoo_chart() -> None:
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1700000000, 1700000060],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0, 101.0],
                                "high": [101.0, 102.0],
                                "low": [99.0, 100.0],
                                "close": [100.5, 101.5],
                                "volume": [1000, 1100],
                            }
                        ]
                    },
                }
            ]
        }
    }
    bars = _parse_yahoo_chart("AAPL", "yahoo", payload)
    assert len(bars) == 2
    assert bars[0].symbol == "AAPL"
    assert bars[0].close == 100.5


def test_registry_fallback_to_yahoo() -> None:
    registry = ProviderRegistry()
    mock_polygon = MagicMock()
    mock_polygon.provider_id = "polygon"
    mock_polygon.is_configured.return_value = True
    mock_polygon.fetch_bars.return_value = type(
        "R", (), {"success": False, "bars": [], "error": "fail"}
    )()
    mock_yahoo = MagicMock()
    mock_yahoo.provider_id = "yahoo"
    mock_yahoo.is_configured.return_value = True
    mock_yahoo.fetch_bars.return_value = type(
        "R",
        (),
        {
            "success": True,
            "bars": [BarRecord("AAPL", "yahoo", 1, 1, 1, 1, 1, 1)],
            "error": "",
        },
    )()
    registry._providers["polygon"] = mock_polygon
    registry._providers["yahoo"] = mock_yahoo

    # Force only polygon in backfill role then fallback
    result = registry.fetch_bars_with_fallback("AAPL", 0, 100, role="backfill")
    assert result.success
    assert result.bars[0].provider == "yahoo"


def test_yahoo_provider_configured() -> None:
    assert YahooProvider().is_configured() is True
