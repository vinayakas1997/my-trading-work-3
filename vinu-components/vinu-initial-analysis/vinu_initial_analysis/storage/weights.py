from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import torch


class WeightsStore:
    """Trained-model artifact store for walk-forward backtest steps.

    Layout (see 05-storage-enhancement-levels/plan.md):
      {data_root}/weights/{symbol}/{angle_name}/{timeframe}/{YYYY}/{YYYYMM}/{bar_ts}.pt

    Sharded by year/month so one folder never accumulates the hundreds of
    thousands of files a multi-year, 1-minute-resolution backtest would
    otherwise produce in a single flat directory (DLinear's design doc:
    one weights file per walk-forward step).

    `torch.save`/`torch.load` are used for every payload, not just PyTorch
    state_dicts — torch is already a hard dependency of this project (7
    angles train PyTorch models) and `torch.save` already pickles arbitrary
    picklable Python objects when they aren't tensors, so a separate plain
    pickling path would add no real capability, only a second code path.
    """

    def __init__(self, data_root: str | Path) -> None:
        self._root = Path(data_root) / "weights"

    def save(
        self,
        symbol: str,
        angle_name: str,
        timeframe: str,
        bar_ts: int,
        weights: Any,
    ) -> str:
        """Saves `weights` and returns its weights_ref.

        weights_ref is the full path relative to `{data_root}/weights/`
        (e.g. "AAPL/dlinear/1D/2024/202405/1715779800.pt") — deliberately
        the whole relative path, not the bare filename, so it alone is
        enough to `load()` the exact model back later without separately
        having to remember which symbol/angle/timeframe/month it came from.
        """
        dt = datetime.fromtimestamp(bar_ts, tz=timezone.utc)
        rel_path = Path(symbol) / angle_name / timeframe / f"{dt.year:04d}" / f"{dt.year:04d}{dt.month:02d}" / f"{bar_ts}.pt"
        full_path = self._root / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        torch.save(weights, full_path)
        return rel_path.as_posix()

    def load(self, weights_ref: str) -> Any:
        """Loads back whatever `save()` stored for this weights_ref."""
        full_path = self._root / weights_ref
        return torch.load(full_path, weights_only=False)
