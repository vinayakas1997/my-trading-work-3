import json
import logging
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from vinu_infra.debug import JsonFormatter, setup_logging


@pytest.fixture(autouse=True)
def _reset_root_logging():
    yield
    for h in list(logging.getLogger().handlers):
        h.close()
        logging.getLogger().removeHandler(h)


def _read_lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_json_formatter_produces_parseable_line():
    record = logging.LogRecord(
        name="vinu.test", level=logging.INFO, pathname=__file__, lineno=1,
        msg="hello %s", args=("world",), exc_info=None,
    )
    record.vinu_service = "vinu-test"
    record.vinu_ctx = {"ticker": "AAPL"}
    line = JsonFormatter().format(record)
    data = json.loads(line)
    assert data["level"] == "INFO"
    assert data["service"] == "vinu-test"
    assert data["logger"] == "vinu.test"
    assert data["message"] == "hello world"
    assert data["ticker"] == "AAPL"
    assert "ts" in data


def test_json_formatter_handles_record_without_ctx():
    record = logging.LogRecord(
        name="vinu.test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="plain", args=(), exc_info=None,
    )
    data = json.loads(JsonFormatter().format(record))
    assert data["message"] == "plain"
    assert data["service"] == ""


def test_json_formatter_includes_traceback_on_exception():
    record = logging.LogRecord(
        name="vinu.test", level=logging.ERROR, pathname=__file__, lineno=1,
        msg="boom", args=(), exc_info=(ZeroDivisionError, ZeroDivisionError("x"), None),
    )
    data = json.loads(JsonFormatter().format(record))
    assert data["exc_type"] == "ZeroDivisionError"
    assert "ZeroDivisionError" in data["traceback"]


def test_setup_logging_writes_structured_jsonl_with_context_and_exception():
    with TemporaryDirectory() as tmp:
        structured = Path(tmp) / "vinu-structured.log"
        setup_logging("vinu-test", structured_path=str(structured))

        logger = logging.getLogger("vinu.worker.sample")
        logger.info(
            "cycle complete",
            extra={"vinu_ctx": {"worker": "sample-worker", "tickers_checked": 3}},
        )
        try:
            1 / 0
        except ZeroDivisionError:
            logger.exception(
                "cycle failed",
                extra={"vinu_ctx": {"worker": "sample-worker"}},
            )

        lines = _read_lines(structured)
        assert len(lines) == 2

        info = lines[0]
        assert info["level"] == "INFO"
        assert info["service"] == "vinu-test"
        assert info["logger"] == "vinu.worker.sample"
        assert info["worker"] == "sample-worker"
        assert info["tickers_checked"] == 3

        error = lines[1]
        assert error["level"] == "ERROR"
        assert error["exc_type"] == "ZeroDivisionError"
        assert "ZeroDivisionError" in error["traceback"]