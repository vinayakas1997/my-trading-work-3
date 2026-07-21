"""Sync global .env → per-service .env files.

Reads variables from vinu-components/.env (global) and merges them into each
service's .env, using the service's .env.example as a template.

Usage:
    python sync-env.py                     # generate all service .env files
    python sync-env.py --dry-run           # show what would be written
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import IO

ROOT = Path(__file__).resolve().parent

SERVICES = [
    "vinu-news",
    "vinu-stock-price",
    "vinu-tools",
    "vinu-initial-analysis",
    "vinu-strategy",
    "vinu-simulator",
    "vinu-research",
]


def parse_env(lines: list[str]) -> dict[str, str]:
    """Parse a .env file into a dict, preserving comments."""
    result: dict[str, str] = {}
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", line)
        if m:
            key = m.group(1)
            value = m.group(2).strip()
            # Remove surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            result[key] = value
    return result


def write_env(path: Path, pairs: list[tuple[str, str]], dry_run: bool) -> bool:
    """Write key=value pairs to a .env file. Returns True if changes were made."""
    if dry_run:
        print(f"  [dry-run] would write {path} ({len(pairs)} vars)")
        return True

    existing = {}
    if path.exists():
        existing = parse_env(path.read_text().splitlines())

    changed = False
    for key, value in pairs:
        if existing.get(key) != value:
            changed = True
            break

    if not changed:
        return False

    lines: list[str] = []
    for key, value in pairs:
        lines.append(f"{key}={value}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


def merge_and_write(
    global_env: dict[str, str],
    example_path: Path,
    env_path: Path,
    dry_run: bool,
) -> bool:
    """Merge global values into a service .env using .example as template."""
    if not example_path.exists():
        print(f"  ⚠  {example_path} not found, skipping")
        return False

    example_lines = example_path.read_text(encoding="utf-8").splitlines()
    pairs: list[tuple[str, str]] = []
    keys_seen: set[str] = set()

    for line in example_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)", stripped)
        if m:
            key = m.group(1)
            # Global wins if present
            value = global_env.get(key, m.group(2).strip())
            pairs.append((key, value))
            keys_seen.add(key)

    return write_env(env_path, pairs, dry_run)


def generate_service_envs(global_env: dict[str, str], dry_run: bool) -> None:
    for svc in SERVICES:
        example_path = ROOT / svc / ".env.example"
        env_path = ROOT / svc / ".env"
        print(f"  {svc}: ", end="")
        changed = merge_and_write(global_env, example_path, env_path, dry_run)
        print("synced" if changed else "unchanged")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    global_path = ROOT / ".env"
    if not global_path.exists():
        print(f"ERROR: {global_path} not found. Create it first.")
        sys.exit(1)

    global_env = parse_env(global_path.read_text().splitlines())
    print(f"Loaded {len(global_env)} variables from {global_path.name}")

    if dry_run:
        print("\n[Dry run — no files will be written]\n")
    else:
        print()

    generate_service_envs(global_env, dry_run)

    if not dry_run:
        print("\nDone. Run: docker compose up -d")


if __name__ == "__main__":
    main()
