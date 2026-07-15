"""Reset catalog for fresh backfill."""
import sqlite3

db = r'C:\Users\vinay\Desktop\my-trading-work-3\data\stock-price\meta.db'
con = sqlite3.connect(db)
cur = con.cursor()

cur.execute('UPDATE symbol_catalog SET first_bar_ts = NULL, last_bar_ts = NULL, archive_through = NULL, backfill_status = "pending"')
cur.execute('DELETE FROM backfill_jobs')
cur.execute('DELETE FROM ingest_log')
con.commit()

cur.execute('SELECT symbol, backfill_status, archive_through, first_bar_ts FROM symbol_catalog')
print('After reset:')
for row in cur.fetchall():
    print(f'  {row[0]}: status={row[1]}, archive_through={row[2]}, first_bar_ts={row[3]}')

con.close()
