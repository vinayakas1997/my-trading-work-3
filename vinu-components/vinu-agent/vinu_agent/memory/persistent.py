from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MemoryEntry:
    name: str
    content: str
    memory_type: str = "finding"
    description: str = ""
    created_at: str = ""


class PersistentMemory:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._entries: Dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        for path in self.base_dir.glob("*.md"):
            name = path.stem
            content = path.read_text()
            self._entries[name] = MemoryEntry(
                name=name,
                content=content,
                memory_type="finding",
            )

    def add(
        self,
        name: str,
        content: str,
        memory_type: str = "finding",
        description: str = "",
    ) -> MemoryEntry:
        import time
        entry = MemoryEntry(
            name=name,
            content=content,
            memory_type=memory_type,
            description=description or content[:100],
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._entries[name] = entry
        self._save(entry)
        return entry

    def _save(self, entry: MemoryEntry) -> None:
        path = self.base_dir / f"{entry.name}.md"
        path.write_text(entry.content)

    def find_relevant(self, query: str, max_results: int = 3) -> List[MemoryEntry]:
        query_lower = query.lower()
        scored = []
        for entry in self._entries.values():
            score = 0
            if query_lower in entry.name.lower():
                score += 3
            if query_lower in entry.content.lower():
                score += 2
            if query_lower in entry.description.lower():
                score += 1
            if score > 0:
                scored.append((score, entry))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [e for _, e in scored[:max_results]]

    def to_summary(self) -> str:
        if not self._entries:
            return "No memories stored."
        lines = ["## Persistent Memory"]
        for entry in self._entries.values():
            lines.append(f"- {entry.name}: {entry.description}")
        return "\n".join(lines)
