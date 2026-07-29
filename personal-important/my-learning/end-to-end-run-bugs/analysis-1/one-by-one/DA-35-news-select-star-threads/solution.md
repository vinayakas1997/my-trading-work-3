# DA-35 🟡 `SELECT *` on Threads/Snapshots Tables

See [DA-34 solution](../DA-34-SELECT-star-from-articles/solution.md) — completed together in the same fix.

**Summary:** Replaced `SELECT *` with explicit `THREAD_COLUMNS` (10 columns) and `SNAPSHOT_COLUMNS` (7 columns) in `repository.py`:
- `get_active_threads` — `story_threads` 
- `get_thread` — `story_threads`
- `get_thread_timeline` — `thread_daily_snapshots`

52 news tests pass.
