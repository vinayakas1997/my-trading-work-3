"""Read a running service's SQLite store from INSIDE its container.

Never open data/<service>/*.db from Windows while the stack is up: the container uses WAL (shared-memory locking) and a
host process on the other side of the bind mount is not part of that locking. My own 20-second host-side poller made the
agent's planner and significance workers die with `sqlite3.OperationalError: disk I/O error` on startup, which cost a
planner cycle each time. Reading through the container keeps one side of the lock.

    python scripts/stack_db.py agent-api team_runs.db "select status, count(*) from team_runs group by 1"

The file name is looked up in the container's data dir (/data; override with STACK_DB_DIR). A full /path is not taken as an
argument because Git Bash rewrites it into a Windows path.
"""
from __future__ import annotations

import os
import subprocess
import sys

CODE = (
    "import sqlite3,sys;c=sqlite3.connect(sys.argv[1],timeout=5);"
    "cur=c.execute(sys.argv[2]);print([d[0] for d in cur.description]);"
    "[print(r) for r in cur.fetchall()]"
)


def main() -> int:
    if len(sys.argv) != 4:
        print(__doc__)
        return 2
    service, name, sql = sys.argv[1:]
    path = os.environ.get("STACK_DB_DIR", "/data").rstrip("/") + "/" + name
    return subprocess.call(["docker", "compose", "exec", "-T", service, "python", "-c", CODE, path, sql])


if __name__ == "__main__":
    sys.exit(main())
