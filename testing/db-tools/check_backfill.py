"""Check backfill progress in meta.db"""
import sqlite3
import os

db = r'C:\Users\vinay\Desktop\my-trading-work-3\data\stock-price\meta.db'
print(f"DB path: {db}")
print(f"DB exists: {os.path.exists(db)}")
print(f"DB size: {os.path.getsize(db)}")

con = sqlite3.connect(db)
cur = con.cursor()

cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cur.fetchall()]
print(f"\nTables: {tables}")

for table in tables:
    cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    desc = [d[0] for d in cur.description]
    print(f"\n=== {table} ({len(rows)} rows) ===")
    for r in rows:
        print(dict(zip(desc, r)))

con.close()
