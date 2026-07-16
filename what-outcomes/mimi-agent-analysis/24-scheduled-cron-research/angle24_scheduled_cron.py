"""Angle 24: Scheduled/Cron Research — cron parsing, next run calc, task persistence."""
import sys, json, time
sys.path.insert(0, '/home/somic_cps/Vina/my-trading-work-3/vinu-components')

from datetime import datetime, timedelta, timezone
import calendar

def log(label, elapsed, status, detail=''):
    print(json.dumps({"step": label, "time_s": round(elapsed, 3), "status": status, "detail": str(detail)[:600]}))

# ── Step 1: Cron Parsing (manual implementation) ──
print("=== STEP 1: CRON PARSING ===")
t0 = time.time()
def parse_cron_field(field, min_val, max_val):
    if field == '*':
        return list(range(min_val, max_val + 1))
    if '/' in field:
        parts = field.split('/')
        step = int(parts[1])
        if parts[0] == '*':
            return list(range(min_val, max_val + 1, step))
        start = int(parts[0])
        return list(range(start, max_val + 1, step))
    if ',' in field:
        return [int(x) for x in field.split(',')]
    if '-' in field:
        s, e = field.split('-')
        return list(range(int(s), int(e) + 1))
    return [int(field)]

def parse_cron(expr):
    fields = expr.strip().split()
    if len(fields) != 5:
        return None
    return {
        'minute': parse_cron_field(fields[0], 0, 59),
        'hour': parse_cron_field(fields[1], 0, 23),
        'day': parse_cron_field(fields[2], 1, 31),
        'month': parse_cron_field(fields[3], 1, 12),
        'weekday': parse_cron_field(fields[4], 0, 6),
    }

cron_tests = [
    ('0 2 * * 1-5', 'weekdays 2AM'),
    ('0 0 * * 0', 'sunday midnight'),
    ('*/30 * * * *', 'every 30 min'),
    ('0 9 * * 1-5', 'weekdays 9AM'),
    ('0 0 1 * *', 'first of month'),
]
for expr, desc in cron_tests:
    t1 = time.time()
    parsed = parse_cron(expr)
    if parsed:
        summary = {k: f'{len(v)} values [{min(v)}-{max(v)}]' for k, v in parsed.items()}
        log(f'cron_{desc[:15]}', time.time()-t1, 'PASS', summary)
    else:
        log(f'cron_{desc[:15]}', time.time()-t1, 'FAIL', 'Invalid cron expression')

# ── Step 2: Next Run Time Calculator ──
print("\n=== STEP 2: NEXT RUN TIME ===")
t0 = time.time()
def next_run(expr, from_time=None):
    if from_time is None:
        from_time = datetime.now(timezone.utc)
    parsed = parse_cron(expr)
    if not parsed:
        return None
    candidates = []
    for minute in parsed['minute']:
        for hour in parsed['hour']:
            for day in parsed['day']:
                for month in parsed['month']:
                    for weekday in parsed['weekday']:
                        try:
                            dt = from_time.replace(month=month, day=day, hour=hour, minute=minute, second=0, microsecond=0)
                            if dt.weekday() == weekday and dt > from_time:
                                candidates.append(dt)
                        except (ValueError, OverflowError):
                            pass
    return min(candidates) if candidates else None

exprs = ['0 2 * * 1-5', '0 0 * * 0', '*/30 * * * *']
for expr in exprs:
    t1 = time.time()
    nxt = next_run(expr)
    if nxt:
        log(f'next_{expr[:10]}', time.time()-t1, 'PASS', f'next={nxt.isoformat()}')
    else:
        log(f'next_{expr[:10]}', time.time()-t1, 'WARN', 'No upcoming run found')

# ── Step 3: Task Persistence (SQLite) ──
print("\n=== STEP 3: TASK PERSISTENCE ===")
t0 = time.time()
try:
    import sqlite3
    db = sqlite3.connect(':memory:')
    db.execute('''CREATE TABLE IF NOT EXISTS scheduled_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        cron TEXT NOT NULL,
        task_type TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        last_run TEXT,
        next_run TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )''')
    tasks = [
        ('daily_decay_check', '0 2 * * 1-5', 'decay_monitoring'),
        ('weekly_backtest', '0 0 * * 0', 'backtest'),
        ('daily_research', '0 9 * * 1-5', 'research_loop'),
    ]
    for name, cron, ttype in tasks:
        db.execute('INSERT INTO scheduled_tasks (name, cron, task_type) VALUES (?, ?, ?)',
                   (name, cron, ttype))
    db.commit()
    rows = db.execute('SELECT * FROM scheduled_tasks').fetchall()
    log('task_persistence', time.time()-t0, 'PASS', f'{len(rows)} tasks stored in SQLite')
    for r in rows:
        log(f'task_{r[1]}', 0, 'PASS', f'cron={r[2]}, type={r[3]}, enabled={r[4]}')
    db.close()
except Exception as e:
    log('task_persistence', time.time()-t0, 'FAIL', str(e))

# ── Step 4: Module Import Test ──
print("\n=== STEP 4: VINU_RESEARCH.SCHEDULED ===")
t0 = time.time()
try:
    from vinu_research.scheduled.cron import CronParser
    cp = CronParser()
    for expr, desc in cron_tests:
        p = cp.parse(expr)
        log(f'cronparser_{desc[:15]}', time.time()-t0, 'PASS', str(p)[:200])
except Exception as e:
    log('scheduled_module', time.time()-t0, 'WARN', f'vinu_research.scheduled not importable: {e}')

# Verify directory exists
t0 = time.time()
import os
scheduled_dir = '/home/somic_cps/Vina/my-trading-work-3/vinu-components/vinu-research/vinu_research/scheduled'
if os.path.isdir(scheduled_dir):
    files = [f for f in os.listdir(scheduled_dir) if f.endswith('.py')]
    log('scheduled_dir', time.time()-t0, 'PASS', f'Files on disk: {files}')
else:
    log('scheduled_dir', time.time()-t0, 'WARN', 'Directory not found')

print('\n=== DONE ===')
log('total', 0, 'COMPLETE', 'Angle 24 scheduled/cron research finished')
