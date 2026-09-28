"""item #11 finding #5: fetch_chain didn't distinguish 429/5xx (retryable)
from 401/403 (permanent) -- both came back as the same generic
{"status": "error"}, so a calling LLM couldn't tell whether retrying
makes sense. Previously zero test coverage on this file at all."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import requests

from vinu_agent.tools.options_tool import OptionsGreeksTool, RetryableOptionsError, fetch_chain


def _response(status_code: int, json_body: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_body or {}
    resp.raise_for_status = MagicMock()
    if status_code >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(f"HTTP {status_code}")
    return resp


def _with_credentials():
    return patch.multiple(
        "vinu_agent.tools.options_tool",
        ALPACA_API_KEY="key", ALPACA_API_SECRET="secret",
    )


class TestFetchChainErrorClassification:
    def test_401_raises_permission_error(self) -> None:
        with _with_credentials(), patch("requests.get", return_value=_response(401)):
            try:
                fetch_chain("AAPL")
                assert False, "expected PermissionError"
            except PermissionError as exc:
                assert "401" in str(exc)

    def test_403_also_raises_permission_error(self) -> None:
        """The finding's own text groups 401 and 403 together as
        permanent -- 403 used to fall through to a generic HTTPError via
        raise_for_status() instead of getting this same treatment."""
        with _with_credentials(), patch("requests.get", return_value=_response(403)):
            try:
                fetch_chain("AAPL")
                assert False, "expected PermissionError"
            except PermissionError as exc:
                assert "403" in str(exc)

    def test_429_raises_retryable_options_error(self) -> None:
        with _with_credentials(), patch("requests.get", return_value=_response(429)):
            try:
                fetch_chain("AAPL")
                assert False, "expected RetryableOptionsError"
            except RetryableOptionsError as exc:
                assert "429" in str(exc)

    def test_500_raises_retryable_options_error(self) -> None:
        with _with_credentials(), patch("requests.get", return_value=_response(500)):
            try:
                fetch_chain("AAPL")
                assert False, "expected RetryableOptionsError"
            except RetryableOptionsError as exc:
                assert "500" in str(exc)

    def test_503_raises_retryable_options_error(self) -> None:
        with _with_credentials(), patch("requests.get", return_value=_response(503)):
            try:
                fetch_chain("AAPL")
                assert False, "expected RetryableOptionsError"
            except RetryableOptionsError:
                pass

    def test_404_raises_a_plain_http_error_not_retryable(self) -> None:
        """A permanent, non-credential failure (bad symbol, etc.) --
        neither PermissionError nor RetryableOptionsError, so it falls
        into the generic "not retryable" bucket."""
        with _with_credentials(), patch("requests.get", return_value=_response(404)):
            try:
                fetch_chain("AAPL")
                assert False, "expected an HTTPError"
            except RetryableOptionsError:
                assert False, "404 must not be classified as retryable"
            except PermissionError:
                assert False, "404 must not be classified as a permission error"
            except requests.HTTPError:
                pass

    def test_connect_error_raises_retryable_options_error(self) -> None:
        with _with_credentials(), patch("requests.get", side_effect=requests.ConnectionError("dropped")):
            try:
                fetch_chain("AAPL")
                assert False, "expected RetryableOptionsError"
            except RetryableOptionsError as exc:
                assert "ConnectionError" in str(exc)

    def test_timeout_raises_retryable_options_error(self) -> None:
        with _with_credentials(), patch("requests.get", side_effect=requests.Timeout("slow")):
            try:
                fetch_chain("AAPL")
                assert False, "expected RetryableOptionsError"
            except RetryableOptionsError:
                pass

    def test_200_returns_parsed_rows(self) -> None:
        body = {
            "snapshots": {
                "AAPL240119C00190000": {
                    "latestQuote": {"bp": 1.0, "ap": 1.2},
                    "greeks": {"delta": 0.5, "gamma": 0.1, "theta": -0.02, "vega": 0.3, "rho": 0.01},
                    "impliedVolatility": 0.32,
                }
            }
        }
        with _with_credentials(), patch("requests.get", return_value=_response(200, body)):
            rows = fetch_chain("AAPL")
        assert len(rows) == 1
        assert rows[0]["contract_symbol"] == "AAPL240119C00190000"
        assert rows[0]["mid"] == 1.1
        assert rows[0]["delta"] == 0.5

    def test_no_credentials_raises_value_error(self) -> None:
        with patch.multiple("vinu_agent.tools.options_tool", ALPACA_API_KEY="", ALPACA_API_SECRET=""):
            try:
                fetch_chain("AAPL")
                assert False, "expected ValueError"
            except ValueError:
                pass


class TestOptionsGreeksToolRetryableField:
    def test_retryable_failure_sets_retryable_true(self) -> None:
        with patch(
            "vinu_agent.tools.options_tool.fetch_chain",
            side_effect=RetryableOptionsError("HTTP 503 (retryable)"),
        ):
            result = json.loads(OptionsGreeksTool().execute(symbol="AAPL"))
        assert result["status"] == "error"
        assert result["retryable"] is True

    def test_permanent_failure_sets_retryable_false(self) -> None:
        with patch(
            "vinu_agent.tools.options_tool.fetch_chain",
            side_effect=PermissionError("no entitlement"),
        ):
            result = json.loads(OptionsGreeksTool().execute(symbol="AAPL"))
        assert result["status"] == "error"
        assert result["retryable"] is False

    def test_as_of_set_returns_unavailable_before_any_fetch(self) -> None:
        tool = OptionsGreeksTool()
        tool._as_of = "2024-01-01T00:00:00Z"
        with patch("vinu_agent.tools.options_tool.fetch_chain") as mock_fetch:
            result = json.loads(tool.execute(symbol="AAPL"))
        assert result["status"] == "unavailable"
        mock_fetch.assert_not_called()

    def test_empty_chain_reports_empty_status(self) -> None:
        with patch("vinu_agent.tools.options_tool.fetch_chain", return_value=[]):
            result = json.loads(OptionsGreeksTool().execute(symbol="ZZZZ"))
        assert result["status"] == "empty"

    def test_ok_result_includes_contracts(self) -> None:
        rows = [{"contract_symbol": "AAPL240119C00190000"}]
        with patch("vinu_agent.tools.options_tool.fetch_chain", return_value=rows):
            result = json.loads(OptionsGreeksTool().execute(symbol="AAPL"))
        assert result["status"] == "ok"
        assert result["n_contracts"] == 1


class TestPerInstanceCaching:
    """item #11 finding #4: repeated identical fetches within one agent
    loop must not re-hit the network every time."""

    def test_identical_call_twice_only_fetches_once(self) -> None:
        tool = OptionsGreeksTool()
        rows = [{"contract_symbol": "AAPL240119C00190000"}]
        with patch("vinu_agent.tools.options_tool.fetch_chain", return_value=rows) as mock_fetch:
            first = tool.execute(symbol="AAPL")
            second = tool.execute(symbol="AAPL")
        assert mock_fetch.call_count == 1
        assert first == second

    def test_error_result_is_not_cached(self) -> None:
        """A transient failure must not lock a bad answer in for the rest
        of the run -- a later identical call should retry, not replay the
        cached error."""
        tool = OptionsGreeksTool()
        with patch(
            "vinu_agent.tools.options_tool.fetch_chain",
            side_effect=RetryableOptionsError("boom"),
        ) as mock_fetch:
            tool.execute(symbol="AAPL")
        rows = [{"contract_symbol": "AAPL240119C00190000"}]
        with patch("vinu_agent.tools.options_tool.fetch_chain", return_value=rows) as mock_fetch2:
            result = json.loads(tool.execute(symbol="AAPL"))
        assert mock_fetch2.call_count == 1
        assert result["status"] == "ok"

    def test_empty_result_is_not_cached(self) -> None:
        tool = OptionsGreeksTool()
        with patch("vinu_agent.tools.options_tool.fetch_chain", return_value=[]):
            tool.execute(symbol="ZZZZ")
        rows = [{"contract_symbol": "AAPL240119C00190000"}]
        with patch("vinu_agent.tools.options_tool.fetch_chain", return_value=rows) as mock_fetch:
            result = json.loads(tool.execute(symbol="ZZZZ"))
        assert mock_fetch.call_count == 1
        assert result["status"] == "ok"
