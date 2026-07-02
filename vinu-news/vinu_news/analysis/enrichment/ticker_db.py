"""Local caching and loading of the free ticker database from GitHub."""

from __future__ import annotations

import csv
import logging
import sqlite3
import time
from pathlib import Path
import requests

from vinu_news.config import load_config

LOG = logging.getLogger(__name__)

URL = "https://raw.githubusercontent.com/adanos-software/free-ticker-database/main/data/tickers.csv"
CACHE_EXPIRY_SECONDS = 30 * 24 * 60 * 60  # 30 days

# In-memory CSV cache for fallback mode (e.g. in test environments)
_csv_alias_to_ticker: dict[str, str] | None = None
_csv_ticker_to_aliases: dict[str, list[str]] | None = None


def get_ticker_data_path() -> tuple[Path, bool]:
    """
    Return path to tickers.csv and a boolean indicating if a fresh download occurred.
    """
    downloaded = False
    try:
        config = load_config()
        db_dir = config.db_path.parent
        local_file = db_dir / "tickers.csv"
        db_dir.mkdir(parents=True, exist_ok=True)
    except Exception:
        local_file = Path.cwd() / "data" / "tickers.csv"
        try:
            local_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

    # Check if local file exists and is recent enough
    if local_file.exists():
        try:
            file_age = time.time() - local_file.stat().st_mtime
            if file_age < CACHE_EXPIRY_SECONDS:
                return local_file, downloaded
        except Exception as exc:
            LOG.warning("Failed to check file mtime for %s: %s", local_file, exc)

    # Download fresh file
    LOG.info("Downloading fresh ticker database from GitHub...")
    try:
        resp = requests.get(URL, timeout=30)
        resp.raise_for_status()
        local_file.write_text(resp.text, encoding="utf-8")
        downloaded = True
        return local_file, downloaded
    except Exception as exc:
        LOG.error(
            "Failed to download ticker database: %s. Falling back to local copy if available.",
            exc,
        )
        if local_file.exists():
            return local_file, downloaded
        raise exc


def sync_ticker_db_if_needed(conn: sqlite3.Connection) -> None:
    """Seed the SQLite ticker_reference table from CSV if empty or CSV is new."""
    try:
        cursor = conn.execute("SELECT COUNT(*) FROM ticker_reference")
        count = cursor.fetchone()[0]
    except sqlite3.OperationalError:
        # Table might not exist yet (e.g. if schema has not run)
        return

    try:
        path, downloaded = get_ticker_data_path()
    except Exception as exc:
        LOG.error("Could not obtain ticker database path: %s", exc)
        return

    if count > 0 and not downloaded:
        return

    LOG.info("Syncing ticker_reference table from CSV...")

    ticker_to_aliases: dict[str, set[str]] = {}
    ticker_to_name: dict[str, str] = {}

    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row.get("ticker", "").strip().upper()
                name = row.get("name", "").strip()
                aliases_str = row.get("aliases", "").strip()

                if not ticker or not name:
                    continue

                ticker_to_name[ticker] = name
                if ticker not in ticker_to_aliases:
                    ticker_to_aliases[ticker] = set()

                ticker_to_aliases[ticker].add(name.upper())
                if aliases_str:
                    for alias in aliases_str.split("|"):
                        alias_cleaned = alias.strip().upper()
                        if alias_cleaned:
                            ticker_to_aliases[ticker].add(alias_cleaned)
    except Exception as exc:
        LOG.error("Failed to read tickers.csv for database seeding: %s", exc)
        return

    # Merge manual overrides
    manual_aliases = {
        "GOOGL": ["GOOGLE", "ALPHABET"],
        "GOOG": ["GOOGLE", "ALPHABET"],
        "AAPL": ["APPLE"],
        "MSFT": ["MICROSOFT"],
        "AMZN": ["AMAZON"],
        "NVDA": ["NVIDIA"],
        "TSLA": ["TESLA"],
        "META": ["META", "FACEBOOK"],
        "NFLX": ["NETFLIX"],
    }
    for t, aliases in manual_aliases.items():
        t_upper = t.upper()
        if t_upper not in ticker_to_name:
            ticker_to_name[t_upper] = t_upper
        if t_upper not in ticker_to_aliases:
            ticker_to_aliases[t_upper] = set()
        for alias in aliases:
            ticker_to_aliases[t_upper].add(alias.upper())

    # Perform bulk database insert
    rows_to_insert = []
    for ticker, name in ticker_to_name.items():
        aliases_set = ticker_to_aliases.get(ticker, set())
        aliases_str = "|".join(sorted(aliases_set))
        rows_to_insert.append((ticker, name, aliases_str))

    try:
        conn.execute("BEGIN TRANSACTION")
        conn.executemany(
            "INSERT OR REPLACE INTO ticker_reference (ticker, name, aliases) VALUES (?, ?, ?)",
            rows_to_insert,
        )
        conn.commit()
        LOG.info("Successfully synced %d ticker reference rows.", len(rows_to_insert))
    except Exception as exc:
        conn.rollback()
        LOG.error("Failed to commit ticker_reference sync: %s", exc)


def _load_mappings_from_csv() -> tuple[dict[str, str], dict[str, list[str]]]:
    """Parse CSV mappings and cache them in memory as a fallback."""
    global _csv_alias_to_ticker, _csv_ticker_to_aliases
    if _csv_alias_to_ticker is not None and _csv_ticker_to_aliases is not None:
        return _csv_alias_to_ticker, _csv_ticker_to_aliases

    alias_to_ticker: dict[str, str] = {}
    ticker_to_aliases: dict[str, list[str]] = {}

    try:
        path, _ = get_ticker_data_path()
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ticker = row.get("ticker", "").strip().upper()
                name = row.get("name", "").strip()
                aliases_str = row.get("aliases", "").strip()

                if not ticker or not name:
                    continue

                name_upper = name.upper()
                name_lower = name.lower()
                alias_to_ticker[name_lower] = ticker
                aliases_list = [name_upper]

                if aliases_str:
                    for part in aliases_str.split("|"):
                        part_cleaned = part.strip()
                        if part_cleaned:
                            part_upper = part_cleaned.upper()
                            part_lower = part_cleaned.lower()
                            alias_to_ticker[part_lower] = ticker
                            if part_upper not in aliases_list:
                                aliases_list.append(part_upper)

                ticker_to_aliases[ticker] = aliases_list

        # Merge manual overrides
        manual_aliases = {
            "GOOGL": ["GOOGLE", "ALPHABET"],
            "GOOG": ["GOOGLE", "ALPHABET"],
            "AAPL": ["APPLE"],
            "MSFT": ["MICROSOFT"],
            "AMZN": ["AMAZON"],
            "NVDA": ["NVIDIA"],
            "TSLA": ["TESLA"],
            "META": ["META", "FACEBOOK"],
            "NFLX": ["NETFLIX"],
        }
        for t, aliases in manual_aliases.items():
            t_upper = t.upper()
            if t_upper not in ticker_to_aliases:
                ticker_to_aliases[t_upper] = []
            for alias in aliases:
                alias_upper = alias.upper()
                alias_lower = alias.lower()
                alias_to_ticker[alias_lower] = t_upper
                if alias_upper not in ticker_to_aliases[t_upper]:
                    ticker_to_aliases[t_upper].append(alias_upper)

        _csv_alias_to_ticker = alias_to_ticker
        _csv_ticker_to_aliases = ticker_to_aliases
    except Exception as exc:
        LOG.error("Fallback CSV load failed: %s", exc)
        return {}, {}

    return _csv_alias_to_ticker, _csv_ticker_to_aliases


def get_mappings_for_tickers(
    tickers: set[str],
    conn: sqlite3.Connection | None = None,
) -> tuple[dict[str, str], dict[str, list[str]]]:
    """
    Query database for mappings of the specified tickers.
    If database table is missing (e.g. in test env), falls back to CSV parsing.
    """
    if not tickers:
        return {}, {}

    alias_to_ticker: dict[str, str] = {}
    ticker_to_aliases: dict[str, list[str]] = {}

    close_conn = False
    if conn is None:
        try:
            config = load_config()
            conn = sqlite3.connect(config.db_path)
            close_conn = True
        except Exception as exc:
            LOG.error("Failed to connect to SQLite in get_mappings_for_tickers: %s", exc)
            # Fallback to CSV
            csv_alias_to_ticker, csv_ticker_to_aliases = _load_mappings_from_csv()
            for ticker in tickers:
                ticker_upper = ticker.upper()
                if ticker_upper in csv_ticker_to_aliases:
                    ticker_to_aliases[ticker_upper] = csv_ticker_to_aliases[ticker_upper]
                    for alias, t in csv_alias_to_ticker.items():
                        if t == ticker_upper:
                            alias_to_ticker[alias] = ticker_upper
            return alias_to_ticker, ticker_to_aliases

    try:
        placeholders = ",".join("?" for _ in tickers)
        query = f"SELECT ticker, name, aliases FROM ticker_reference WHERE ticker IN ({placeholders})"
        cursor = conn.execute(query, list(tickers))
        for row in cursor.fetchall():
            if isinstance(row, dict) or hasattr(row, "keys"):
                ticker = row["ticker"]
                name = row["name"]
                aliases_str = row["aliases"]
            else:
                ticker, name, aliases_str = row

            ticker_upper = ticker.upper()
            aliases_list = []

            name_lower = name.lower()
            alias_to_ticker[name_lower] = ticker_upper
            aliases_list.append(name.upper())

            if aliases_str:
                for alias in aliases_str.split("|"):
                    alias_cleaned = alias.strip()
                    if alias_cleaned:
                        alias_to_ticker[alias_cleaned.lower()] = ticker_upper
                        if alias_cleaned.upper() not in aliases_list:
                            aliases_list.append(alias_cleaned.upper())

            ticker_to_aliases[ticker_upper] = aliases_list
    except sqlite3.OperationalError as exc:
        LOG.warning("ticker_reference table not found, falling back to CSV: %s", exc)
        csv_alias_to_ticker, csv_ticker_to_aliases = _load_mappings_from_csv()
        for ticker in tickers:
            ticker_upper = ticker.upper()
            if ticker_upper in csv_ticker_to_aliases:
                ticker_to_aliases[ticker_upper] = csv_ticker_to_aliases[ticker_upper]
                for alias, t in csv_alias_to_ticker.items():
                    if t == ticker_upper:
                        alias_to_ticker[alias] = ticker_upper
    except Exception as exc:
        LOG.error("Error querying ticker mappings: %s", exc)
    finally:
        if close_conn and conn:
            conn.close()

    return alias_to_ticker, ticker_to_aliases


def load_ticker_mappings() -> tuple[dict[str, str], dict[str, list[str]]]:
    """For backwards compatibility, load mappings for default major tickers."""
    from vinu_news.analysis.enrichment.ticker_extractor import DEFAULT_MAJOR_TICKERS

    return get_mappings_for_tickers(DEFAULT_MAJOR_TICKERS)
