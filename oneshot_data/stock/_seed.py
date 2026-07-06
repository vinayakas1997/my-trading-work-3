import sqlite3, pyarrow as pa, pyarrow.parquet as pq, time, os
conn = sqlite3.connect("/data/meta.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("PRAGMA busy_timeout=30000")
conn.execute("CREATE TABLE IF NOT EXISTS symbol_catalog (symbol TEXT PRIMARY KEY, provider TEXT, first_bar_ts INTEGER, last_bar_ts INTEGER, archive_through TEXT, live_file TEXT, backfill_status TEXT, updated_at INTEGER, has_adj_data INTEGER, gap_count INTEGER, last_validation_at INTEGER)")
conn.execute("CREATE TABLE IF NOT EXISTS watchlist_tickers (ticker TEXT PRIMARY KEY, added_at INTEGER)")
conn.execute("CREATE TABLE IF NOT EXISTS vinu_settings (key TEXT PRIMARY KEY, value TEXT)")
now_ts = int(time.time())
base_ts = now_ts - 90 * 86400
conn.execute("INSERT OR REPLACE INTO vinu_settings VALUES ('poll_interval_sec','60')")
conn.execute("INSERT OR REPLACE INTO vinu_settings VALUES ('default_provider','test')")
conn.execute("INSERT OR REPLACE INTO vinu_settings VALUES ('data_root','/data')")
symbols = ["AAPL", "TSLA", "NVDA"]
for sym in symbols:
    conn.execute("INSERT OR REPLACE INTO symbol_catalog VALUES (?,?,?,?,?,?,?,?,?,?,?)", (sym, "test", base_ts, now_ts, None, None, "complete", now_ts, 0, 0, now_ts))
    conn.execute("INSERT OR REPLACE INTO watchlist_tickers VALUES (?,?)", (sym, now_ts))
conn.commit()
for sym in symbols:
    bars = []
    for i in range(92):
        bar_ts = base_ts + i * 86400
        cp = 100.0 + i * 0.5 + (1.5 if i % 3 == 0 else -0.5) + (hash(sym) % 20 - 10)
        bars.append({"symbol": sym, "provider": "test", "bar_ts": int(bar_ts), "open": float(cp-0.5), "high": float(cp+1.2), "low": float(cp-1.2), "close": float(cp), "volume": 1500000.0, "vwap": float(cp), "trades": 120, "adj_factor": 1.0})
    fields = [("symbol", pa.string()), ("provider", pa.string()), ("bar_ts", pa.int64()), ("open", pa.float64()), ("high", pa.float64()), ("low", pa.float64()), ("close", pa.float64()), ("volume", pa.float64()), ("vwap", pa.float64()), ("trades", pa.int64()), ("adj_factor", pa.float64())]
    schema = pa.schema(fields)
    table = pa.Table.from_pylist(bars, schema=schema)
    pdir = os.path.join("/data", "prices", "1m", sym, "archive")
    os.makedirs(pdir, exist_ok=True)
    pq.write_table(table, os.path.join(pdir, "2026.parquet"))
    print(f"Seeded {sym}: {len(bars)} bars")
conn.close()
print("STOCK_SEED_OK")