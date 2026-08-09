"""Cross-storage cleanup for removing an angle entirely.

Both storage trees (`analysis/` results, `weights/` artifacts) key by
{symbol}/{angle_name}/..., so removing an angle isn't a single directory
delete — it's a sweep across every symbol. `RunLog` is a separate SQLite
table with no filesystem link, so it needs its own cleanup too, or
`get_latest_run()` would keep resolving to files that no longer exist. See
05-storage-enhancement-levels/plan.md, "Deleting an angle cleanly".
"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from vinu_initial_analysis.storage.meta import RunLog

_MULTI_DIR = "_multi"


def delete_angle(
    data_root: str | Path,
    angle_name: str,
    run_log: "RunLog | None" = None,
) -> dict[str, int]:
    """Removes every trace of `angle_name`.

    Deletes its `analysis/{symbol}/{angle_name}/` and
    `weights/{symbol}/{angle_name}/` directories for every symbol
    (including multi-ticker `_multi/{ticker_hash}/{angle_name}/`
    subdirectories), then deletes its rows from `run_log` if one is given.

    Returns {"analysis_dirs": n, "weights_dirs": n, "run_log_rows": n}.
    """
    root = Path(data_root)
    removed = {"analysis_dirs": 0, "weights_dirs": 0, "run_log_rows": 0}

    for tree_key, tree_name in (("analysis_dirs", "analysis"), ("weights_dirs", "weights")):
        tree_root = root / tree_name
        if not tree_root.exists():
            continue
        for symbol_dir in tree_root.iterdir():
            if not symbol_dir.is_dir():
                continue
            if symbol_dir.name == _MULTI_DIR:
                candidates = [d / angle_name for d in symbol_dir.iterdir() if d.is_dir()]
            else:
                candidates = [symbol_dir / angle_name]
            for angle_dir in candidates:
                if angle_dir.exists():
                    shutil.rmtree(angle_dir)
                    removed[tree_key] += 1

    if run_log is not None:
        removed["run_log_rows"] = run_log.delete_by_angle(angle_name)

    return removed
