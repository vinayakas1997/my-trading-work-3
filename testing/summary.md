# Testing Summary

## alpaca-try/ — Alpaca API & IEX Feed Tests

| File | What It Achieves |
|---|---|
| `test_alpaca_api.py` | Verifies Alpaca v2 stocks/bars endpoint connectivity & API auth |
| `test_backfill.py` | Tests the exact `fetch_bars` flow used by production backfill (AAPL 1Min) |
| `test_1min_years.py` | Probes Alpaca year-by-year (2020–2025) for earliest 1Min bar (AAPL, IEX) |
| `test_2022_backfill.py` | Downloads full year 2022 of 1Min AAPL bars with pagination |
| `test_earliest.py` | Tests `earliest_available` logic for 1Min AAPL bars over last year |
| `test_year_pagination.py` | Downloads full year 2024 of 1Min AAPL bars via pagination with IEX fallback |
| `test_daily_probe.py` | Probes 1Day AAPL bars 2020–present, prints counts/results |
| `test_daily_iex.py` | Tests earliest-available logic for 1Day IEX bars across multiple symbols |
| `test_iex.py` | Tests 1Min bars with explicit `feed=iex` to verify IEX fallback |
| `test_news.py` | Tests Alpaca News API (`v1beta1/news`) fetching latest articles |

## discovery/ — Discovery Orchestrator Tests

| File | What It Achieves |
|---|---|
| `test_discover.py` | Calls `_discover_first_year()` for several symbols, inspects catalog output |
| `test_discover2.py` | Debugs config object attrs, then runs `_discover_first_year()` similarly |

## db-tools/ — Database Introspection, Fix & Seed Scripts

| File | What It Achieves |
|---|---|
| `check_backfill.py` | Connects to `meta.db`, lists all tables and dumps every row |
| `check_backfill2.py` | Reads `backfill_jobs` and `symbol_catalog` tables for job/archive status |
| `check_db.py` | Connects to `news.db`, prints tables, row counts, columns, sample rows |
| `fix_data.py` | Recovers `news.db` from its WAL file, inspects recovered tables |
| `seed_data.py` | Fetches daily bars for multiple symbols via Alpaca SDK, writes to local storage |
| `reset_catalog.py` | Resets `symbol_catalog`, `backfill_jobs`, `ingest_log` tables to clean state |
