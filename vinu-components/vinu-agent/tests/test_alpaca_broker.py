from unittest.mock import MagicMock, patch

from vinu_agent.broker.alpaca import AlpacaBroker


def _mock_session_post(broker: AlpacaBroker, json_body=None):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = json_body or {"id": "order1", "status": "accepted"}
    broker._session.post = MagicMock(return_value=resp)
    return broker._session.post


class TestSubmitOrderBracket:
    def test_plain_order_has_no_order_class(self) -> None:
        broker = AlpacaBroker()
        mock_post = _mock_session_post(broker)

        broker.submit_order(symbol="AAPL", qty=10, side="buy")

        payload = mock_post.call_args.kwargs["json"]
        assert "order_class" not in payload
        assert "take_profit" not in payload
        assert "stop_loss" not in payload

    def test_both_legs_produces_bracket_order(self) -> None:
        broker = AlpacaBroker()
        mock_post = _mock_session_post(broker)

        broker.submit_order(
            symbol="AAPL", qty=10, side="buy",
            take_profit_price=150.0, stop_loss_price=130.0,
        )

        payload = mock_post.call_args.kwargs["json"]
        assert payload["order_class"] == "bracket"
        assert payload["take_profit"] == {"limit_price": "150.0"}
        assert payload["stop_loss"] == {"stop_price": "130.0"}

    def test_stop_loss_only_produces_oto_order(self) -> None:
        broker = AlpacaBroker()
        mock_post = _mock_session_post(broker)

        broker.submit_order(symbol="AAPL", qty=10, side="buy", stop_loss_price=130.0)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["order_class"] == "oto"
        assert payload["stop_loss"] == {"stop_price": "130.0"}
        assert "take_profit" not in payload

    def test_stop_loss_with_limit_price(self) -> None:
        broker = AlpacaBroker()
        mock_post = _mock_session_post(broker)

        broker.submit_order(
            symbol="AAPL", qty=10, side="buy",
            stop_loss_price=130.0, stop_loss_limit_price=129.5,
        )

        payload = mock_post.call_args.kwargs["json"]
        assert payload["stop_loss"] == {"stop_price": "130.0", "limit_price": "129.5"}

    def test_take_profit_only_produces_oto_order(self) -> None:
        broker = AlpacaBroker()
        mock_post = _mock_session_post(broker)

        broker.submit_order(symbol="AAPL", qty=10, side="buy", take_profit_price=150.0)

        payload = mock_post.call_args.kwargs["json"]
        assert payload["order_class"] == "oto"
        assert payload["take_profit"] == {"limit_price": "150.0"}
        assert "stop_loss" not in payload


class TestGetClock:
    def test_returns_clock_payload(self) -> None:
        broker = AlpacaBroker()
        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"is_open": True, "next_open": "x", "next_close": "y"}
        broker._session.get = MagicMock(return_value=resp)

        clock = broker.get_clock()

        assert clock["is_open"] is True
        broker._session.get.assert_called_once()
        assert broker._session.get.call_args.args[0].endswith("/v2/clock")
