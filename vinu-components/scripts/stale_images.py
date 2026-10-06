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
    committed = run("git", "log", "-1", "--format=%ct|%h|%s", "--", *rel, *skip).strip()
    if committed:
        ts, sha, subject = committed.split("|", 2)
        newest, what = float(ts), f"commit {sha} {subject[:60]}"
    # `git status` prints paths relative to the REPOSITORY root, which is not ROOT when this folder is a subdirectory
    # of the repo; joining them to ROOT pointed at files that do not exist, so uncommitted edits were never noticed.
    top = Path(run("git", "rev-parse", "--show-toplevel").strip() or ROOT)
    for line in run("git", "status", "--porcelain", "--", *rel, *skip).splitlines():
        f = top / line[3:].strip().strip('"')
        if f.is_file() and f.stat().st_mtime > newest:
            newest, what = f.stat().st_mtime, f"uncommitted edit {line[3:].strip()}"
    return newest, what


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
        built_at = parse_time(run("docker", "image", "inspect", "-f", "{{.Created}}", running_image))
        problems = []
        if changed_at > built_at:
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
