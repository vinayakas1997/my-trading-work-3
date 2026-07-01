"""Tests for CLI --continuous flag."""

from unittest.mock import MagicMock, patch

import pytest

from vinu_news.cli import ingest_main


@patch("vinu_news.cli.time.sleep", side_effect=KeyboardInterrupt)
@patch("vinu_news.cli.NewsService")
def test_continuous_uses_db_poll_interval(mock_service_cls, mock_sleep):
    mock_instance = MagicMock()
    mock_instance.run_ingestion_cycle.return_value = MagicMock(format_report=lambda: "ok")
    mock_instance.run_ticker_news_ingest.return_value = MagicMock(format_report=lambda: "ok")
    mock_instance.get_settings.return_value.poll_interval_sec = 120
    mock_instance.pop_pending_ticker_fetch.return_value = []
    mock_service_cls.return_value.__enter__.return_value = mock_instance

    with pytest.raises(KeyboardInterrupt):
        ingest_main(["--continuous"])

    # The sleep is chunked (tick_sec=2) so it can be cut short if the
    # interval shrinks mid-wait; the first chunk is min(tick_sec, interval).
    mock_sleep.assert_called_once_with(2)
