import json
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


class TraceWriter:
    def __init__(self, trace_dir: str = "", session_id: str = ""):
        self._lock = threading.Lock()
        self._entries: List[Dict[str, Any]] = []
        self._session_id = session_id
        if trace_dir:
            Path(trace_dir).mkdir(parents=True, exist_ok=True)
            self._filepath = str(Path(trace_dir) / f"trace_{session_id}_{int(time.time())}.jsonl")
        else:
            self._filepath = ""

    def append(self, entry: Dict[str, Any]) -> None:
        entry["ts"] = time.time()
        with self._lock:
            self._entries.append(entry)
            if self._filepath:
                try:
                    with open(self._filepath, "a") as f:
                        f.write(json.dumps(entry, default=str) + "\n")
                except OSError:
                    pass

    def snapshot(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._entries)

    def close(self) -> None:
        if self._filepath:
            try:
                with open(self._filepath.replace(".jsonl", ".meta.json"), "w") as f:
                    json.dump({
                        "session_id": self._session_id,
                        "entry_count": len(self._entries),
                        "finalized": True,
                    }, f)
            except OSError:
                pass
