from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from vinu_initial_analysis.storage.weights import WeightsStore


def test_save_returns_sharded_relative_path():
    with TemporaryDirectory() as tmp:
        store = WeightsStore(tmp)
        ref = store.save("AAPL", "dlinear", "1D", 1715779800, {"w": [1.0]})
        assert ref == "AAPL/dlinear/1D/2024/202405/1715779800.pt"
        assert (Path(tmp) / "weights" / ref).exists()


def test_save_and_load_round_trips_arbitrary_object():
    with TemporaryDirectory() as tmp:
        store = WeightsStore(tmp)
        payload = {"a": [1, 2, 3], "b": "hello"}
        ref = store.save("MSFT", "lstm", "1H", 1715779800, payload)
        loaded = store.load(ref)
        assert loaded == payload


def test_different_months_shard_into_different_folders():
    with TemporaryDirectory() as tmp:
        store = WeightsStore(tmp)
        ref_may = store.save("AAPL", "dlinear", "1D", 1715779800, {"w": 1})  # 2024-05
        ref_june = store.save("AAPL", "dlinear", "1D", 1718000000, {"w": 2})  # 2024-06
        assert ref_may.split("/")[-2] != ref_june.split("/")[-2]


def test_weights_ref_is_self_sufficient_for_reload():
    with TemporaryDirectory() as tmp:
        store = WeightsStore(tmp)
        ref = store.save("AAPL", "dlinear", "1D", 1715779800, {"w": 42})
        # A fresh store instance, only given the ref string, must still
        # resolve to the same file -- that's the point of storing the full
        # relative path (not just the bare filename) as weights_ref.
        other_store = WeightsStore(tmp)
        assert other_store.load(ref) == {"w": 42}
