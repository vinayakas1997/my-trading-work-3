"""Check backfill jobs in meta.db"""
import sqlite3

db = r'C:\Users\vinay\Desktop\my-trading-work-3\data\stock-price\meta.db'
con = sqlite3.connect(db)
cur = con.cursor()

cur.execute("SELECT * FROM backfill_jobs")
rows = cur.fetchall()
desc = [d[0] for d in cur.description]
print(f"Jobs ({len(rows)}):")
for r in rows:
    print(dict(zip(desc, r)))

cur.execute("SELECT symbol, backfill_status, archive_through, first_bar_ts, last_bar_ts FROM symbol_catalog")
print("\nCatalog:")
for r in cur.fetchall():
    print(f"{r[0]}: status={r[1]}, archive_through={r[2]}")

con.close()
