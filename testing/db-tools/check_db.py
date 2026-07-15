import sqlite3, pathlib

db_path = pathlib.Path(r'C:\Users\vinay\Desktop\my-trading-work-3\vinu-components\data\news\news.db')
if not db_path.exists():
    print(f"DB not found at {db_path}")
    exit()

db = sqlite3.connect(str(db_path))
cursor = db.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = cursor.fetchall()
print('Tables:', tables)
for t in tables:
    name = t[0]
    try:
        count = db.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]
        print(f'  {name}: {count} rows')
        if count > 0:
            cols = db.execute(f'SELECT * FROM "{name}" LIMIT 1').description
            col_names = [c[0] for c in cols]
            print(f'    Columns: {col_names[:20]}')
            sample = db.execute(f'SELECT * FROM "{name}" LIMIT 3').fetchall()
            for row in sample:
                print(f'    Row: {row[:5]}...')
    except Exception as e:
        print(f'  {name}: Error - {e}')
db.close()
