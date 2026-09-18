from __future__ import annotations

import json

from vinu_infra.ticker_profile import read_ticker_profile, write_ticker_profile_key


class TestWriteAndReadRoundTrip:
    def test_round_trip(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "aapl", "vinu_stock_price", {"gap_count": 0})

        profile = read_ticker_profile(tmp_path, "AAPL")
        assert profile["symbol"] == "AAPL"
        assert profile["vinu_stock_price"]["gap_count"] == 0
        assert "updated_at" in profile["vinu_stock_price"]

    def test_symbol_is_normalized_to_uppercase_in_file_path(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "msft", "vinu_screener", {"final_score": 1.2})
        assert (tmp_path / "ticker-profiles" / "MSFT.json").is_file()


class TestMergeAcrossServices:
    def test_second_service_key_does_not_clobber_first(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_stock_price", {"gap_count": 0})
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_screener", {"final_score": 1.2})

        profile = read_ticker_profile(tmp_path, "AAPL")
        assert profile["vinu_stock_price"]["gap_count"] == 0
        assert profile["vinu_screener"]["final_score"] == 1.2

    def test_rewriting_own_key_replaces_only_that_key(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_stock_price", {"gap_count": 5})
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_screener", {"final_score": 1.2})
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_stock_price", {"gap_count": 0})

        profile = read_ticker_profile(tmp_path, "AAPL")
        assert profile["vinu_stock_price"]["gap_count"] == 0
        assert profile["vinu_screener"]["final_score"] == 1.2


class TestBestEffort:
    def test_read_missing_file_returns_empty_dict(self, tmp_path) -> None:
        assert read_ticker_profile(tmp_path, "AAPL") == {}

    def test_read_with_no_shared_root_returns_empty_dict(self) -> None:
        assert read_ticker_profile(None, "AAPL") == {}

    def test_write_with_no_shared_root_is_a_silent_noop(self) -> None:
        write_ticker_profile_key(None, "AAPL", "vinu_stock_price", {"gap_count": 0})  # must not raise

    def test_read_corrupt_json_returns_empty_dict(self, tmp_path) -> None:
        path = tmp_path / "ticker-profiles" / "AAPL.json"
        path.parent.mkdir(parents=True)
        path.write_text("{not valid json", encoding="utf-8")
        assert read_ticker_profile(tmp_path, "AAPL") == {}

    def test_write_to_unwritable_root_does_not_raise(self, tmp_path) -> None:
        blocked_root = tmp_path / "some_file_not_a_dir"
        blocked_root.write_text("x", encoding="utf-8")
        write_ticker_profile_key(blocked_root, "AAPL", "vinu_stock_price", {"gap_count": 0})  # must not raise

    def test_write_non_json_serializable_value_does_not_raise(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_stock_price", {"weird": object()})  # must not raise


class TestFileShape:
    def test_written_file_is_valid_indented_json(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_stock_price", {"gap_count": 0})
        path = tmp_path / "ticker-profiles" / "AAPL.json"
        raw = path.read_text(encoding="utf-8")
        assert json.loads(raw)["vinu_stock_price"]["gap_count"] == 0

    def test_lock_file_created_alongside(self, tmp_path) -> None:
        write_ticker_profile_key(tmp_path, "AAPL", "vinu_stock_price", {"gap_count": 0})
        assert (tmp_path / "ticker-profiles" / "AAPL.json.lock").exists()
