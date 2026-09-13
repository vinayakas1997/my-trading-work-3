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


@patch("vinu_news.cli.NewsService")
def test_core_cycle_exception_is_caught_and_loop_continues(mock_service_cls, capsys):
    """Finding #20: an unhandled exception from run_rss_cycle/
    run_ticker_cycle/sync_and_backfill must not kill the whole ingest
    worker process -- it should be logged and the loop should reach a
    second cycle instead of propagating.

    `setup_logging()` reconfigures the root logger's handlers as part of
    `ingest_main`, which detaches pytest's own caplog handler -- so the
    logged output is asserted via the real stderr stream (capsys) instead
    of caplog. The poll interval is set to 0 so the inner wait loop (which
    is not what's under test here) breaks immediately without needing to
    mock `time.sleep`; the second `run_ingestion_cycle` call raises
    `KeyboardInterrupt` directly (a `BaseException`, not caught by the
    `except Exception` under test) purely to end the `while True` loop
    cleanly once the resilience behavior has been observed.
    """
    mock_instance = MagicMock()
    # First call (inside run_rss_cycle's `with NewsService() as service:`)
    # raises; everything after must still be reachable on a later cycle.
    mock_instance.run_ingestion_cycle.side_effect = [RuntimeError("rss boom"), KeyboardInterrupt]
    mock_instance.run_ticker_news_ingest.return_value = MagicMock(format_report=lambda: "ok")
    mock_instance.get_settings.return_value.poll_interval_sec = 0
    mock_instance.pop_pending_ticker_fetch.return_value = []
    mock_instance.get_poll_status.return_value = MagicMock(last_poll_finished_at=None)
    mock_service_cls.return_value.__enter__.return_value = mock_instance
    # A MagicMock's default __exit__ return value is itself a (truthy)
    # MagicMock, which would silently *suppress* the exception raised
    # inside the `with NewsService() as service:` block -- force it falsy
    # so the exception actually propagates out to ingest_main's try/except.
    mock_service_cls.return_value.__exit__.return_value = False

    with pytest.raises(KeyboardInterrupt):
        ingest_main(["--continuous"])

    err = capsys.readouterr().err
    assert "rss boom" in err
    assert "Ingest cycle failed" in err
    # The loop survived the first cycle's exception and reached a second
    # cycle's run_ingestion_cycle call (which raises the KeyboardInterrupt
    # that ends the test).
    assert mock_instance.run_ingestion_cycle.call_count == 2
