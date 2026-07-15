from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .frontmatter import parse_frontmatter


@dataclass
class Skill:
    name: str
    description: str = ""
    category: str = "other"
    body: str = ""
    dir_path: Optional[Path] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def load_support_file(self, filename: str) -> Optional[str]:
        if not self.dir_path:
            return None
        path = self.dir_path / filename
        if path.exists():
            return path.read_text()
        return None


class SkillsLoader:
    CATEGORY_ORDER = [
        "data-source", "strategy", "analysis", "asset-class",
        "crypto", "flow", "tool", "other",
    ]

    def __init__(
        self,
        skills_dir: Optional[Path] = None,
        user_skills_dir: Optional[Path] = None,
    ) -> None:
        self._skills: Dict[str, Skill] = {}

        if skills_dir and skills_dir.exists():
            self._load_from_dir(skills_dir)

        if user_skills_dir and user_skills_dir.exists():
            self._load_from_dir(user_skills_dir)

    def _load_from_dir(self, directory: Path) -> None:
        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_md = skill_dir / "SKILL.md"
            if not skill_md.exists():
                continue

            content = skill_md.read_text()
            metadata, body = parse_frontmatter(content)

            skill = Skill(
                name=skill_dir.name,
                description=metadata.get("description", ""),
                category=metadata.get("category", "other"),
                body=body,
                dir_path=skill_dir,
                metadata=metadata,
            )
            self._skills[skill.name] = skill

    def get_descriptions(self) -> str:
        by_category: Dict[str, List[str]] = {}
        for skill in self._skills.values():
            by_category.setdefault(skill.category, []).append(
                f"- {skill.name}: {skill.description}"
            )

        lines = []
        for cat in self.CATEGORY_ORDER:
            if cat in by_category:
                lines.append(f"\n**{cat.upper()}:**")
                lines.extend(by_category[cat])

        for cat, skills in by_category.items():
            if cat not in self.CATEGORY_ORDER:
                lines.append(f"\n**{cat.upper()}:**")
                lines.extend(skills)

        return "\n".join(lines)

    def get_content(self, name: str) -> Optional[str]:
        skill = self._skills.get(name)
        if not skill:
            return None
        return f'<skill name="{name}">\n{skill.body}\n</skill>'
