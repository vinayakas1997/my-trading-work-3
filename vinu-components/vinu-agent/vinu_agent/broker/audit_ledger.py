"""Hash-chained, fsynced, append-only audit ledger for the highest-stakes
safety events -- kill-switch halt/resume, emergency flatten (Stage A, A37;
pattern from Vibe-Trading's ``governance/ledger.py``).

``kill_switch.py``'s ``AuditLogger`` already writes a JSONL trail, but a
plain log can be edited after the fact with no trace. This ledger chains
each entry's hash into the next (``hash_n = sha256(hash_{n-1} + payload_n)``),
so altering, reordering, or deleting *any* past record breaks the hash of
every record after it and ``verify()`` reports exactly where. Each append
is ``fsync``'d before returning, so a record that a caller was told is
written survives a power loss.

Deliberately separate from ``AuditLogger``: that one is a broad,
high-volume operational log (every order, every risk check); this is a
low-volume, tamper-evident record of the few events where "was this
tampered with?" is a question anyone would actually ask.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

GENESIS_HASH = "0" * 64

DEFAULT_LEDGER_PATH = Path(
    os.environ.get(
        "VINU_AGENT_AUDIT_LEDGER",
        os.environ.get("VINU_AGENT_DATA_ROOT", str(Path.home() / ".vinu")) + "/safety_ledger.jsonl",
    )
)


def _canonical(obj: dict) -> str:
    """Stable serialization -- sorted keys, no incidental whitespace -- so
    the hash of a record is reproducible byte-for-byte on re-read."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _entry_hash(prev_hash: str, core: dict) -> str:
    return hashlib.sha256((prev_hash + "\n" + _canonical(core)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LedgerVerification:
    ok: bool
    entries: int
    broken_at: int | None = None
    reason: str = ""


class HashChainedLedger:
    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path is not None else DEFAULT_LEDGER_PATH
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path

    # -- write --------------------------------------------------------
    def append(self, event_type: str, payload: dict | None = None) -> dict:
        """Append one event, fsync, and return the written entry (including
        its ``seq``/``prev_hash``/``hash``). Never raises on a write problem
        -- a failed audit write must not take down the halt it's recording;
        it logs and returns the entry it *tried* to write."""
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                prev_hash, seq = self._tail()
                core = {
                    "seq": seq,
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "event_type": event_type,
                    "payload": payload or {},
                }
                entry = {**core, "prev_hash": prev_hash, "hash": _entry_hash(prev_hash, core)}
                line = json.dumps(entry, default=str) + "\n"
                with open(self._path, "a", encoding="utf-8") as f:
                    if sys.platform != "win32":
                        import fcntl

                        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                    try:
                        f.write(line)
                        f.flush()
                        os.fsync(f.fileno())
                    finally:
                        if sys.platform != "win32":
                            import fcntl

                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                logger.info("SAFETY LEDGER %d: %s %s", seq, event_type, _canonical(payload or {}))
                return entry
            except Exception:
                logger.exception("failed to append %s to the safety ledger", event_type)
                return {"seq": -1, "event_type": event_type, "payload": payload or {}, "hash": ""}

    def _tail(self) -> tuple[str, int]:
        """(prev_hash, next_seq) from the current file end. Genesis when empty."""
        if not self._path.exists():
            return GENESIS_HASH, 0
        last_line = ""
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    last_line = line
        if not last_line:
            return GENESIS_HASH, 0
        last = json.loads(last_line)
        return str(last["hash"]), int(last["seq"]) + 1

    # -- read / verify --------------------------------------------
    def entries(self) -> list[dict]:
        if not self._path.exists():
            return []
        out: list[dict] = []
        with open(self._path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    def verify(self) -> LedgerVerification:
        """Walk the chain from genesis. ``ok`` is False at the first entry
        whose recomputed hash, sequence, or ``prev_hash`` link doesn't match."""
        entries = self.entries()
        prev_hash = GENESIS_HASH
        for i, e in enumerate(entries):
            try:
                if int(e["seq"]) != i:
                    return LedgerVerification(False, len(entries), i, f"seq {e.get('seq')} != expected {i}")
                if e.get("prev_hash") != prev_hash:
                    return LedgerVerification(False, len(entries), i, "prev_hash does not match the previous entry's hash")
                core = {"seq": e["seq"], "ts": e["ts"], "event_type": e["event_type"], "payload": e["payload"]}
                if _entry_hash(prev_hash, core) != e.get("hash"):
                    return LedgerVerification(False, len(entries), i, "recomputed hash does not match -- record was altered")
                prev_hash = str(e["hash"])
            except (KeyError, ValueError, TypeError) as exc:
                return LedgerVerification(False, len(entries), i, f"malformed entry: {exc}")
        return LedgerVerification(True, len(entries), None, "chain intact")


_ledger: HashChainedLedger | None = None


def get_safety_ledger() -> HashChainedLedger:
    global _ledger
    if _ledger is None:
        _ledger = HashChainedLedger()
    return _ledger


def reset_safety_ledger(ledger: HashChainedLedger | None = None) -> None:
    """Test hook."""
    global _ledger
    _ledger = ledger
