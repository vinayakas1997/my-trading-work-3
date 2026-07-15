"""Restore news.db from WAL and check stock data."""
import sqlite3, pathlib

news_dir = pathlib.Path(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\data\news')
wal_file = news_dir / 'news.db-wal'
shm_file = news_dir / 'news.db-shm'
db_file = news_dir / 'news.db'

# Try to checkpoint the WAL into a new main db
if wal_file.exists() and not db_file.exists():
    print("Attempting to recover news DB from WAL...")
    # Create empty db file then force checkpoint
    db_file.write_text('')
    conn = sqlite3.connect(str(db_file))
    conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    conn.close()
    
    # Check what we got
    conn = sqlite3.connect(str(db_file))
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = cursor.fetchall()
    print(f"Tables after recovery: {tables}")
    for t in tables:
        name = t[0]
        count = conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f"  {name}: {count} rows")
        if count > 0:
            cols = [c[0] for c in conn.execute(f'SELECT * FROM "{name}" LIMIT 1').description]
            print(f"    Columns: {cols[:15]}")
    conn.close()
else:
    print(f"DB file exists: {db_file.exists()}, WAL exists: {wal_file.exists()}")
    if db_file.exists():
        conn = sqlite3.connect(str(db_file))
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        print(f"Tables: {tables}")
        conn.close()
