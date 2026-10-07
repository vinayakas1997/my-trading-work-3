"""Most of these tests store bars with made-up timestamps (epoch 60, 120, ...), which are not regular-session times. The
candles default is the operator setting VINU_STOCK_DEFAULT_SESSION (regular unless changed); tests that are not about
sessions run with every stored bar visible, and the session behaviour has its own tests (test_session_filter.py)."""
import pytest


@pytest.fixture(autouse=True)
def _every_stored_bar_is_visible_by_default(monkeypatch):
    monkeypatch.setenv("VINU_STOCK_DEFAULT_SESSION", "all")
