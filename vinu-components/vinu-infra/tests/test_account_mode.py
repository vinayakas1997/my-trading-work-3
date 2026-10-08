import pytest

from vinu_infra import account_mode as am


def test_the_default_is_paper_with_no_capital_base(monkeypatch):
    for k in ("VINU_ACCOUNT_MODE", "VINU_REAL_CAPITAL"):
        monkeypatch.delenv(k, raising=False)
    assert am.current_account_mode() == "paper" and am.real_capital() is None


def test_an_unknown_mode_is_refused(monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "live")
    with pytest.raises(ValueError):
        am.current_account_mode()


def test_real_mode_without_a_capital_base_is_refused(monkeypatch):
    monkeypatch.setenv("VINU_ACCOUNT_MODE", "real")
    monkeypatch.delenv("VINU_REAL_CAPITAL", raising=False)
    with pytest.raises(ValueError):
        am.real_capital()


def test_the_capital_base_and_reserve_are_validated(monkeypatch):
    monkeypatch.setenv("VINU_REAL_CAPITAL", "20")
    assert am.real_capital() == 20.0
    monkeypatch.setenv("VINU_REAL_CAPITAL", "-1")
    with pytest.raises(ValueError):
        am.real_capital()
    monkeypatch.setenv("VINU_CAPITAL_RESERVE_FRACTION", "1.5")
    with pytest.raises(ValueError):
        am.reserve_fraction()


def test_a_tag_is_required_and_never_defaulted():
    assert am.require_mode("real") == "real"
    for bad in ("", None, "Paper"):
        with pytest.raises(ValueError):
            am.require_mode(bad)
