#!/usr/bin/env python3
"""Sync vendored package mirrors into the grip-sdk wheel source tree.

The published ``grip-sdk`` distribution must be fully self-contained so that
``pip install grip-sdk`` works without any sibling packages from PyPI. To make
that possible, the canonical sources of ``core``, ``google_ai_search`` and
``grip_engine`` are mirrored into ``packages/sdk/src/`` before the wheel is
built.

Those mirrors are *generated* — never edit them by hand. This script is the
single source of truth for regenerating them, and ``--check`` lets CI fail when
a mirror has drifted from its canonical source.

Usage:
    python scripts/sync_vendored.py          # regenerate mirrors
    python scripts/sync_vendored.py --check  # verify mirrors, non-zero on drift
"""

from __future__ import annotations

import argparse
import filecmp
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# (canonical source, vendored destination)
MIRRORS: list[tuple[Path, Path]] = [
    (ROOT / "packages" / "core" / "src" / "core", ROOT / "packages" / "sdk" / "src" / "core"),
    (
        ROOT / "packages" / "core" / "src" / "google_ai_search",
        ROOT / "packages" / "sdk" / "src" / "google_ai_search",
    ),
    (
        ROOT / "packages" / "engine" / "src" / "grip_engine",
        ROOT / "packages" / "sdk" / "src" / "grip_engine",
    ),
]

# Directories that used to be mirrors but are no longer part of the layout.
STALE_MIRRORS: list[Path] = [
    ROOT / "packages" / "sdk" / "src" / "grip_core",
]

_IGNORE_NAMES = {"__pycache__"}
_IGNORE_SUFFIXES = {".pyc", ".pyo"}


def _is_ignored(path: Path) -> bool:
    return path.name in _IGNORE_NAMES or path.suffix in _IGNORE_SUFFIXES or path.name.endswith(".egg-info")


def _iter_files(base: Path) -> list[Path]:
    """Return sorted relative file paths under *base*, skipping build noise."""
    files: list[Path] = []
    for path in base.rglob("*"):
        if _is_ignored(path):
            continue
        if any(_is_ignored(part) for part in path.parents):
            continue
        if path.is_file():
            files.append(path.relative_to(base))
    return sorted(files)


def _diff(source: Path, dest: Path) -> list[str]:
    """Return human-readable drift entries between source and destination."""
    problems: list[str] = []
    if not dest.exists():
        return [f"missing destination: {dest.relative_to(ROOT)}"]

    source_files = set(_iter_files(source))
    dest_files = set(_iter_files(dest))

    for rel in sorted(source_files - dest_files):
        problems.append(f"missing in mirror: {dest.name}/{rel}")
    for rel in sorted(dest_files - source_files):
        problems.append(f"stale in mirror:   {dest.name}/{rel}")

    for rel in sorted(source_files & dest_files):
        if not filecmp.cmp(source / rel, dest / rel, shallow=False):
            problems.append(f"content differs:   {dest.name}/{rel}")
    return problems


def _sync_one(source: Path, dest: Path) -> int:
    if not source.exists():
        print(f"  ❌ canonical source not found: {source.relative_to(ROOT)}", file=sys.stderr)
        return 1
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(source, dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.egg-info"))
    count = len(_iter_files(dest))
    print(f"  ✅ {source.relative_to(ROOT)}  →  {dest.relative_to(ROOT)}  ({count} files)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync or verify vendored package mirrors.")
    parser.add_argument("--check", action="store_true", help="verify mirrors are in sync (non-zero exit on drift)")
    args = parser.parse_args()

    if args.check:
        print("🔎 Checking vendored mirrors...\n")
        drifted = False
        for source, dest in MIRRORS:
            problems = _diff(source, dest)
            if problems:
                drifted = True
                print(f"  ❌ {dest.relative_to(ROOT)} is out of sync:")
                for problem in problems:
                    print(f"       - {problem}")
            else:
                print(f"  ✅ {dest.relative_to(ROOT)} in sync")
        if drifted:
            print("\n❌ Vendored mirrors drifted. Run: python scripts/sync_vendored.py", file=sys.stderr)
            return 1
        print("\n🎉 All vendored mirrors are in sync.")
        return 0

    print("🔄 Syncing vendored mirrors...\n")
    status = 0
    for stale in STALE_MIRRORS:
        if stale.exists():
            shutil.rmtree(stale)
            print(f"  🧹 removed stale mirror {stale.relative_to(ROOT)}")
    for source, dest in MIRRORS:
        status |= _sync_one(source, dest)
    if status == 0:
        print("\n🎉 Vendored mirrors synced.")
    return status


if __name__ == "__main__":
    sys.exit(main())
