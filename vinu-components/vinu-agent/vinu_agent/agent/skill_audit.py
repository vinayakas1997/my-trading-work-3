"""Phase 6's skill-edit audit log (New-talk-agents/new-thinking/
new-restructure/phases/phase-6-thesis-intake/): records VISIBILITY into
whether risk-relevant skill content changed, not access control -- it
answers "did skills/thesis-intake-risk-rules/SKILL.md change, and when,"
never "who is allowed to change it" (02-guard-rail.md). `skills.py`'s own
`SkillsLoader` has no hook point for this (confirmed by reading it
directly: `_load_from_dir` just reads files once at construction, no
file-watcher, no hashing) -- this is the smallest real addition that
closes the gap without building a live file-watcher this phase has no
real caller/scheduler for yet (same "not wired to a live loop" shape as
Phase 0's RunLog trigger).

Ticker-agnostic by design -- a separate store from TickerLedger, since an
edit to a skill file isn't about one ticker.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from vinu_infra.sqlite import SQLiteBackend

SCHEMA = """
CREATE TABLE IF NOT EXISTS skill_edit_audit (
    entry_id      TEXT PRIMARY KEY,
    skill_path    TEXT NOT NULL,
    detected_at   TEXT NOT NULL,
    old_hash      TEXT NOT NULL DEFAULT '',
    new_hash      TEXT NOT NULL,
    old_line_count INTEGER NOT NULL DEFAULT 0,
    new_line_count INTEGER NOT NULL DEFAULT 0,
    diff_summary  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_skill_edit_audit_path ON skill_edit_audit(skill_path);
"""

SCHEMA_VERSION = 1

# Phase 6's own scope: only the risk-relevant skill is audited, not
# strategy-definitions -- an edit to what shapes strategies exist isn't
# the same kind of event as an edit to what disqualifies a theory outright.
# See 03-test.md: "the audit log is scoped specifically to risk-relevant
# content, not every file in the skill."
AUDITED_SKILL_PATHS: list[str] = [
    "thesis-intake-risk-rules/SKILL.md",
]


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


@dataclass
class SkillEditEntry:
    entry_id: str
    skill_path: str
    detected_at: str
    old_hash: str
    new_hash: str
    old_line_count: int
    new_line_count: int
    diff_summary: str

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "SkillEditEntry":
        return cls(
            entry_id=row["entry_id"], skill_path=row["skill_path"], detected_at=row["detected_at"],
            old_hash=row.get("old_hash", ""), new_hash=row["new_hash"],
            old_line_count=int(row.get("old_line_count") or 0),
            new_line_count=int(row.get("new_line_count") or 0),
            diff_summary=row["diff_summary"],
        )


class SkillAuditStore(SQLiteBackend):
    SCHEMA = SCHEMA
    SCHEMA_VERSION = SCHEMA_VERSION

    def get_latest(self, skill_path: str) -> SkillEditEntry | None:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM skill_edit_audit WHERE skill_path = ? ORDER BY detected_at DESC LIMIT 1",
            (skill_path,),
        ).fetchone()
        return SkillEditEntry.from_row(dict(row)) if row else None

    def get_history(self, skill_path: str) -> list[SkillEditEntry]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM skill_edit_audit WHERE skill_path = ? ORDER BY detected_at ASC",
            (skill_path,),
        ).fetchall()
        return [SkillEditEntry.from_row(dict(r)) for r in rows]

    def record(
        self, skill_path: str, *, old_hash: str, new_hash: str,
        old_line_count: int, new_line_count: int, diff_summary: str,
    ) -> SkillEditEntry:
        entry = SkillEditEntry(
            entry_id=_new_id(), skill_path=skill_path, detected_at=_now(),
            old_hash=old_hash, new_hash=new_hash,
            old_line_count=old_line_count, new_line_count=new_line_count,
            diff_summary=diff_summary,
        )
        self.upsert(
            "skill_edit_audit",
            {
                "entry_id": entry.entry_id, "skill_path": entry.skill_path,
                "detected_at": entry.detected_at, "old_hash": entry.old_hash,
                "new_hash": entry.new_hash, "old_line_count": entry.old_line_count,
                "new_line_count": entry.new_line_count, "diff_summary": entry.diff_summary,
            },
            conflict_columns=["entry_id"],
        )
        return entry


def check_skill_edits(skills_root: Path, audit_store: SkillAuditStore) -> list[SkillEditEntry]:
    """Call on service startup (or periodically, once a real scheduler
    exists -- none does yet, same gap as Phase 0's RunLog trigger). Only
    the paths in AUDITED_SKILL_PATHS are checked. The first time a path is
    ever seen, its hash is recorded as a baseline (not logged as an
    "edit" -- there is nothing to compare it against yet). Returns the
    entries newly recorded this call, empty if nothing changed."""
    newly_recorded: list[SkillEditEntry] = []
    for rel_path in AUDITED_SKILL_PATHS:
        path = skills_root / rel_path
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        new_hash = _content_hash(text)
        new_line_count = text.count("\n") + 1

        latest = audit_store.get_latest(rel_path)
        if latest is None:
            entry = audit_store.record(
                rel_path, old_hash="", new_hash=new_hash,
                old_line_count=0, new_line_count=new_line_count,
                diff_summary="baseline recorded (first time this path was checked)",
            )
            newly_recorded.append(entry)
            continue

        if latest.new_hash != new_hash:
            delta = new_line_count - latest.new_line_count
            sign = "+" if delta >= 0 else ""
            diff_summary = (
                f"content changed: {latest.new_line_count} -> {new_line_count} lines "
                f"({sign}{delta})"
            )
            entry = audit_store.record(
                rel_path, old_hash=latest.new_hash, new_hash=new_hash,
                old_line_count=latest.new_line_count, new_line_count=new_line_count,
                diff_summary=diff_summary,
            )
            newly_recorded.append(entry)

    return newly_recorded
