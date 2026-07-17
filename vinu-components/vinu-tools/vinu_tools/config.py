"""Environment configuration for vinu-tools."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VinuFeaturesConfig:
    data_dir: Path
    meta_db_path: Path
    stock_api_url: str
    host: str
    port: int


def load_config(
    *,
    data_dir: str | None = None,
    meta_db_path: str | None = None,
) -> VinuFeaturesConfig:
    from dotenv import load_dotenv

    load_dotenv()

    data_dir_str = data_dir or os.getenv("VINU_FEATURES_DATA_DIR", "./data")
    data_dir_path = Path(data_dir_str).resolve()
    meta_db_str = meta_db_path or os.getenv("VINU_FEATURES_META_DB_PATH", "")
    meta_db_resolved = Path(meta_db_str).resolve() if meta_db_str else data_dir_path / "meta.db"
    stock_api_url = os.getenv("VINU_STOCK_API_URL", "http://127.0.0.1:8081").rstrip("/")
    host = os.getenv("VINU_FEATURES_HOST", "127.0.0.1")
    port_str = os.getenv("VINU_FEATURES_PORT", "8082")
    try:
        port = int(port_str)
    except ValueError:
        raise ValueError(f"VINU_FEATURES_PORT must be an integer, got {port_str!r}")
    return VinuFeaturesConfig(
        data_dir=data_dir_path,
        meta_db_path=meta_db_resolved,
        stock_api_url=stock_api_url,
        host=host,
        port=port,
    )
