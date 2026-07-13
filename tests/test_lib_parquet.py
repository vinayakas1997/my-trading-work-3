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
