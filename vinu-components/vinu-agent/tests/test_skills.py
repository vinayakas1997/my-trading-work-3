import tempfile
from pathlib import Path

from vinu_agent.agent.frontmatter import parse_frontmatter
from vinu_agent.agent.skills import SkillsLoader, Skill


class TestParseFrontmatter:
    def test_no_frontmatter(self) -> None:
        meta, body = parse_frontmatter("just text")
        assert meta == {}
        assert body == "just text"

    def test_empty_frontmatter(self) -> None:
        meta, body = parse_frontmatter("---\n---\nbody")
        assert meta == {}
        assert body == "body"

    def test_frontmatter_no_newline_after_dashes(self) -> None:
        meta, body = parse_frontmatter("---\nkey: val\n---\nbody")
        assert meta["key"] == "val"
        assert body == "body"

    def test_basic_frontmatter(self) -> None:
        text = """---
title: My Skill
category: analysis
---
Skill body here"""
        meta, body = parse_frontmatter(text)
        assert meta["title"] == "My Skill"
        assert meta["category"] == "analysis"
        assert body == "Skill body here"

    def test_boolean_value(self) -> None:
        text = "---\nenabled: true\n---\nbody"
        meta, body = parse_frontmatter(text)
        assert meta["enabled"] is True

    def test_list_value(self) -> None:
        text = '---\ntags: ["a", "b", "c"]\n---\nbody'
        meta, body = parse_frontmatter(text)
        assert meta["tags"] == ["a", "b", "c"]

    def test_quoted_string(self) -> None:
        text = """---
name: "my skill"
---
body"""
        meta, body = parse_frontmatter(text)
        assert meta["name"] == "my skill"


class TestSkillsLoader:
    def test_load_from_dir(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            skill_dir = Path(tmp) / "my-skill"
            skill_dir.mkdir()
            (skill_dir / "SKILL.md").write_text(
                "---\ndescription: A test skill\n---\nSkill content"
            )
            loader = SkillsLoader(skills_dir=Path(tmp))
            assert "my-skill" in loader._skills
            skill = loader._skills["my-skill"]
            assert skill.description == "A test skill"
            assert skill.body == "Skill content"

    def test_skip_if_no_skilli_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "no-skill"
            d.mkdir()
            (d / "other.txt").write_text("nope")
            loader = SkillsLoader(skills_dir=Path(tmp))
            assert len(loader._skills) == 0

    def test_skip_non_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "notadir").write_text("file")
            loader = SkillsLoader(skills_dir=Path(tmp))
            assert len(loader._skills) == 0

    def test_descriptions_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d1 = Path(tmp) / "skill-a"
            d1.mkdir()
            (d1 / "SKILL.md").write_text(
                "---\ndescription: Skill A desc\ncategory: analysis\n---\nbody"
            )
            d2 = Path(tmp) / "skill-b"
            d2.mkdir()
            (d2 / "SKILL.md").write_text(
                "---\ndescription: Skill B desc\ncategory: data-source\n---\nbody"
            )
            loader = SkillsLoader(skills_dir=Path(tmp))
            desc = loader.get_descriptions()
            assert "skill-a" in desc
            assert "skill-b" in desc
            assert "ANALYSIS" in desc or "analysis" in desc

    def test_get_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "test-skill"
            d.mkdir()
            (d / "SKILL.md").write_text(
                "---\ndescription: Test\n---\nDetailed content here"
            )
            loader = SkillsLoader(skills_dir=Path(tmp))
            content = loader.get_content("test-skill")
            assert content is not None
            assert "Detailed content here" in content

    def test_get_content_missing(self) -> None:
        loader = SkillsLoader()
        assert loader.get_content("nonexistent") is None

    def test_load_support_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "with-support"
            d.mkdir()
            (d / "SKILL.md").write_text("---\ndescription: support\n---\nbody")
            (d / "data.csv").write_text("a,b,c\n1,2,3")
            loader = SkillsLoader(skills_dir=Path(tmp))
            skill = loader._skills["with-support"]
            data = skill.load_support_file("data.csv")
            assert data == "a,b,c\n1,2,3"
            assert skill.load_support_file("nope.txt") is None

    def test_category_order(self) -> None:
        assert SkillsLoader.CATEGORY_ORDER[:3] == ["data-source", "strategy", "analysis"]
