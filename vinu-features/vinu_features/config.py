"""Environment configuration for vinu-features."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class VinuFeaturesConfig:
    data_dir: Path
    meta_db_path: Path
    stock_api_url: str
    host: str
    port: int


def load_config() -> VinuFeaturesConfig:
    data_dir = Path(os.getenv("VINU_FEATURES_DATA_DIR", "./data")).resolve()
    meta_db = os.getenv("VINU_FEATURES_META_DB_PATH", "")
    meta_db_path = Path(meta_db).resolve() if meta_db else data_dir / "meta.db"
    return VinuFeaturesConfig(
        data_dir=data_dir,
        meta_db_path=meta_db_path,
        stock_api_url=os.getenv("VINU_STOCK_API_URL", "http://127.0.0.1:8081").rstrip("/"),
        host=os.getenv("VINU_FEATURES_HOST", "127.0.0.1"),
        port=int(os.getenv("VINU_FEATURES_PORT", "8082")),
    )
