#!/usr/bin/env python3
"""Audit repository for problematic duplicate directory patterns."""

from __future__ import annotations

import os
from pathlib import Path


IGNORE_DIRS = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "__pycache__",
    ".serena",
    ".claude",
}

ALLOWED_NAMED_DIRS = {
    "scripts": {
        "scripts",
        "lifelog-system/scripts",
    },
    "logs": {
        "logs",
        "scripts/logs",
        "lifelog-system/logs",
        "lifelog-system/scripts/logs",
    },
}


def list_directories(repo_root: Path) -> set[str]:
    dirs: set[str] = set()
    for current, dirnames, _ in os.walk(repo_root):
        rel_current = Path(current).relative_to(repo_root)
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        for dirname in dirnames:
            rel = (rel_current / dirname).as_posix()
            dirs.add(rel)
    return dirs


def find_adjacent_duplicate_segments(dirs: set[str]) -> list[str]:
    problematic: list[str] = []
    for rel in sorted(dirs):
        parts = rel.split("/")
        if any(parts[i] == parts[i - 1] for i in range(1, len(parts))):
            problematic.append(rel)
    return problematic


def find_named_dir_violations(dirs: set[str]) -> dict[str, list[str]]:
    violations: dict[str, list[str]] = {}
    for name, allowed in ALLOWED_NAMED_DIRS.items():
        found = sorted(d for d in dirs if Path(d).name == name)
        extra = [d for d in found if d not in allowed]
        if extra:
            violations[name] = extra
    return violations


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    dirs = list_directories(repo_root)

    adjacent_duplicates = find_adjacent_duplicate_segments(dirs)
    named_violations = find_named_dir_violations(dirs)

    print("[audit_duplicate_dirs] repo:", repo_root)
    print("[audit_duplicate_dirs] scanned_dirs:", len(dirs))

    if adjacent_duplicates:
        print("\n[error] Adjacent duplicate directory names detected:")
        for rel in adjacent_duplicates:
            print(" -", rel)

    if named_violations:
        print("\n[error] Unexpected duplicate named directories detected:")
        for name, paths in named_violations.items():
            print(f" - {name}:")
            for rel in paths:
                print("   -", rel)

    if not adjacent_duplicates and not named_violations:
        print("[ok] No problematic duplicate directory patterns found.")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
