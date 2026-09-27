from __future__ import annotations

from collections import OrderedDict
from typing import Any

# item #13 finding #4: identical OHLCV/indicator requests get re-fetched
# from the network on every call, even across a sweep hitting the same
# symbol/date range repeatedly. Same bounded-LRU idiom
# `vinu_research/loop.py`'s own `_LRUCache` already established for its
# feature-snapshot cache -- reimplemented here rather than imported
# cross-service, since neither service depends on the other's package.
_DEFAULT_MAXSIZE = 256


class LRUCache:
    def __init__(self, maxsize: int = _DEFAULT_MAXSIZE):
        self._data: OrderedDict[Any, Any] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: Any) -> Any | None:
        if key not in self._data:
            return None
        self._data.move_to_end(key)
        return self._data[key]

    def set(self, key: Any, value: Any) -> None:
        if key in self._data:
            self._data.move_to_end(key)
        self._data[key] = value
        if len(self._data) > self._maxsize:
            self._data.popitem(last=False)

    def clear(self) -> None:
        self._data.clear()

    def __len__(self) -> int:
        return len(self._data)
