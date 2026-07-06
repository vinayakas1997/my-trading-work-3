"""Shared config loader for alpaca-try scripts."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)


@dataclass(frozen=True)
class AlpacaTryConfig:
    api_key: str
    secret_key: str
    data_base_url: str


def load_config() -> AlpacaTryConfig:
    key = os.environ.get("ALPACA_API_KEY", "")
    secret = os.environ.get("ALPACA_SECRET_KEY", "")
    base_url = os.environ.get(
        "ALPACA_DATA_BASE_URL", "https://data.alpaca.markets"
    )

    if not key or not secret:
        raise RuntimeError(
            "ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env"
        )

    return AlpacaTryConfig(
        api_key=key,
        secret_key=secret,
        data_base_url=base_url,
    )
