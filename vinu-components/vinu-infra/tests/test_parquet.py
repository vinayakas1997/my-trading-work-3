from pathlib import Path
from tempfile import TemporaryDirectory

import pyarrow as pa

from vinu_lib.parquet import ParquetStore


def test_parquet_append_read():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("test/2026.parquet", [
            {"id": "a1", "value": 1},
            {"id": "a2", "value": 2},
        ])
        table = store.read("test/2026.parquet")
        assert table is not None
        assert table.num_rows == 2


def test_parquet_append_merge():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("test/2026.parquet", [{"id": "a1", "value": 1}])
        store.append("test/2026.parquet", [{"id": "a2", "value": 2}])
        table = store.read("test/2026.parquet")
        assert table is not None
        assert table.num_rows == 2


def test_parquet_dedup():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("test/dedup.parquet", [{"id": "a1", "value": 1}],
                     dedup_on=["id"])
        store.append("test/dedup.parquet", [{"id": "a1", "value": 2}],
                     dedup_on=["id"])
        table = store.read("test/dedup.parquet")
        assert table is not None
        assert table.num_rows == 1
        df = table.to_pandas()
        assert df["value"].iloc[0] == 2


def test_parquet_read_nonexistent():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        assert store.read("nonexistent/file.parquet") is None


def test_parquet_compact():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        schema = pa.schema([
            pa.field("id", pa.string()),
            pa.field("value", pa.int64()),
        ])
        store.append("test/compact.parquet", [
            {"id": "a1", "value": 1},
            {"id": "a2", "value": 2},
        ], schema=schema)
        store.compact("test/compact.parquet")
        table = store.read("test/compact.parquet")
        assert table is not None
        assert table.num_rows == 2


def test_read_shard_glob():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("live/AAPL_20260701.parquet", [{"id": "a1", "value": 1}])
        store.append("live/AAPL_20260702.parquet", [{"id": "a2", "value": 2}])
        table = store.read_shard("live/AAPL_*.parquet")
        assert table is not None
        assert table.num_rows == 2


def test_read_shard_nonexistent():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        assert store.read_shard("live/*.parquet") is None


def test_read_shard_dedup():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("live/AAPL_20260701.parquet", [{"id": "a1", "value": 1}])
        store.append("live/AAPL_20260701.parquet", [{"id": "a1", "value": 2}])
        table = store.read_shard("live/AAPL_*.parquet", dedup_on=["id"])
        assert table is not None
        assert table.num_rows == 1
        df = table.to_pandas()
        assert df["value"].iloc[0] == 2


def test_consolidate_merges_correctly():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("live/AAPL_20260701.parquet", [{"id": "a1", "value": 1}])
        store.append("live/AAPL_20260702.parquet", [{"id": "a2", "value": 2}])
        n = store.consolidate("live/AAPL_*.parquet", "archive/AAPL_2026.parquet")
        assert n == 2
        table = store.read("archive/AAPL_2026.parquet")
        assert table is not None
        assert table.num_rows == 2
        remaining = list(Path(tmp).glob("live/AAPL_*.parquet"))
        assert len(remaining) == 0


def test_consolidate_dedups():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        store.append("live/AAPL_20260701.parquet", [{"id": "a1", "value": 1}])
        store.append("live/AAPL_20260701.parquet", [{"id": "a1", "value": 2}])
        n = store.consolidate("live/AAPL_*.parquet", "archive/AAPL_2026.parquet",
                              dedup_on=["id"])
        assert n == 1
        table = store.read("archive/AAPL_2026.parquet")
        assert table is not None
        assert table.num_rows == 1


def test_consolidate_empty_glob():
    with TemporaryDirectory() as tmp:
        store = ParquetStore(tmp)
        n = store.consolidate("nonexistent/*.parquet", "output.parquet")
        assert n == 0
