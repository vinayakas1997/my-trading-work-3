"""Report every compose service whose running container is older than its source code.

A fix only takes effect once the image is rebuilt AND the container is recreated from it.
For each service this compares:
  * the newest change (last commit, or an uncommitted edit) to any path its Dockerfile COPYs,
  * the build time of the image the service's tag points at,
  * whether the running container still uses that image (not an older one after a rebuild).

Usage (from vinu-components/):  python scripts/stale_images.py        # exit 1 if anything is stale
Services in a profile that is not running (models-api) are skipped.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*cmd: str) -> str:
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=False).stdout


def parse_time(value: str) -> float:
    value = re.sub(r"(\.\d{6})\d+", r"\1", value.strip()).replace("Z", "+00:00")
    return datetime.fromisoformat(value).timestamp()


def source_paths(context: str, dockerfile: str) -> list[str]:
    paths: list[str] = []
    for line in Path(dockerfile).read_text(encoding="utf-8").splitlines():
        m = re.match(r"\s*COPY\s+(?:--\S+\s+)*(.+)", line)
        if not m:
            continue
        parts = m.group(1).split()
        for src in parts[:-1]:
            if not src.startswith("--") and not src.startswith("$"):
                paths.append(str(Path(context) / src))
    return paths


def newest_change(paths: list[str]) -> tuple[float, str]:
    newest, what = 0.0, ""
    rel = [str(Path(p).resolve().relative_to(ROOT)) if Path(p).is_absolute() else p for p in paths]
    # Test files never reach a running service, so a tests-only change is not staleness.
    skip = (":(exclude)**/tests/**", ":(exclude)**/test_*.py", ":(exclude)**/*.md")
    # The commit time is deliberately NOT used: committing content that an image was already built from (the normal
    # build, test, then commit order) made every service look stale until the next real change. Anything a checkout, a
    # pull or an edit changes also changes the file's modification time, which is tested below.
    # `git status` prints paths relative to the REPOSITORY root, which is not ROOT when this folder is a subdirectory
    # of the repo; joining them to ROOT pointed at files that do not exist, so uncommitted edits were never noticed.
    top = Path(run("git", "rev-parse", "--show-toplevel").strip() or ROOT)
    for line in run("git", "status", "--porcelain", "--", *rel, *skip).splitlines():
        f = top / line[3:].strip().strip('"')
        if f.is_file() and f.stat().st_mtime > newest:
            newest, what = f.stat().st_mtime, f"uncommitted edit {line[3:].strip()}"
    # Git's view is not the whole truth: it normalises line endings and ignores gitignored files, so a file whose bytes
    # changed (an entrypoint saved with CRLF, which crash-looped its container) can look unchanged to git while the
    # next build would copy different bytes. The modification time of the files a build would actually copy is the
    # direct test.
    mtime, which = newest_mtime(paths)
    if mtime > newest:
        newest, what = mtime, f"file modified {which}"
    return newest, what


_SKIP_DIRS = {"__pycache__", "tests", ".pytest_cache", ".git", "node_modules"}


def newest_mtime(paths: list[str]) -> tuple[float, str]:
    """Newest modification time among the non-test, non-doc files a COPY of `paths` would bring into an image."""
    import os

    best, which = 0.0, ""
    for p in paths:
        p = Path(p) if Path(p).is_absolute() else ROOT / p
        files: list[Path] = []
        if p.is_file():
            files = [p]
        elif p.is_dir():
            for root, dirs, names in os.walk(p):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.endswith(".egg-info")]
                files.extend(Path(root) / n for n in names)
        # A directory's own modification time changes when an entry is added, removed or renamed in it, which no remaining
        # file's time does: moving or deleting a file (a stray package folder, a renamed module) changes what a build
        # copies without touching any file left behind.
        dir_paths = [p] if p.is_dir() else []
        if p.is_dir():
            for root, dirs, _names in os.walk(p):
                dirs[:] = [d for d in dirs if d not in _SKIP_DIRS and not d.endswith(".egg-info")]
                dir_paths.extend(Path(root) / d for d in dirs)
        for d in dir_paths:
            try:
                m = d.stat().st_mtime
            except OSError:
                continue
            if m > best:
                best, which = m, f"directory changed {d.relative_to(ROOT) if ROOT in d.parents else d}"
        for f in files:
            if f.name.startswith("test_") or f.name.endswith((".md", ".pyc")):
                continue
            try:
                m = f.stat().st_mtime
            except OSError:
                continue
            if m > best:
                best, which = m, str(f.relative_to(ROOT)) if ROOT in f.parents else str(f)
    return best, which


def main() -> int:
    cfg = json.loads(run("docker", "compose", "config", "--format", "json"))
    stale: list[str] = []
    for name, svc in sorted(cfg["services"].items()):
        build = svc.get("build")
        if not build:
            continue
        cid = run("docker", "compose", "ps", "-q", name).strip()
        if not cid:
            print(f"  skip   {name:24} (not running)")
            continue
        context = build["context"]
        dockerfile = build.get("dockerfile", "Dockerfile")
        dockerfile = dockerfile if Path(dockerfile).is_absolute() else str(Path(context) / dockerfile)
        changed_at, what = newest_change(source_paths(context, dockerfile))
        running_image = run("docker", "inspect", "-f", "{{.Image}}", cid).strip()
        tag = svc.get("image") or f"{cfg['name']}-{name}"
        tag_image = run("docker", "image", "inspect", "-f", "{{.Id}}", tag).strip()
        created = run("docker", "image", "inspect", "-f", "{{.Created}}", running_image).strip()
        problems = []
        if not created:
            # the container's image id is gone (an older build was replaced and pruned): it is by definition not the
            # current build. This used to crash the whole check with "Invalid isoformat string".
            built_at = 0.0
            problems.append("the container's image no longer exists; recreate it")
        else:
            built_at = parse_time(created)
        if built_at and changed_at > built_at:
            problems.append(f"source changed after the image was built ({what})")
        if tag_image and running_image != tag_image:
            problems.append("container runs an older image than the current build; recreate it")
        status = "STALE" if problems else "ok"
        print(f"  {status:6} {name:24} built {datetime.fromtimestamp(built_at, timezone.utc):%m-%d %H:%M}Z  " + "; ".join(problems))
        if problems:
            stale.append(name)
    if stale:
        print(f"\n{len(stale)} stale: {' '.join(stale)}\nRebuild and recreate: docker compose build {' '.join(stale)} && docker compose up -d {' '.join(stale)}")
        return 1
    print("\nevery running service is built from its current source")
    return 0


if __name__ == "__main__":
    sys.exit(main())
