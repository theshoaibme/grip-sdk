#!/usr/bin/env python3
"""Build script for Grip Platform packages."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PACKAGES = [
    ROOT / "packages" / "core",
    ROOT / "packages" / "engine",
    ROOT / "packages" / "sdk",
]


def sync_vendored() -> bool:
    print("🔄 Syncing vendored mirrors before build...")
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "sync_vendored.py")], cwd=ROOT)
    return result.returncode == 0


def build_package(pkg_path: Path) -> bool:
    print(f"📦 Building package in {pkg_path.relative_to(ROOT)}...")
    cmd = [sys.executable, "-m", "build", "--wheel", "--sdist", str(pkg_path)]
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode == 0


def main() -> int:
    print("🚀 Starting Grip Platform Build Pipeline\n")
    if not sync_vendored():
        print("❌ Failed to sync vendored mirrors", file=sys.stderr)
        return 1
    success = True
    for pkg in PACKAGES:
        if (pkg / "pyproject.toml").exists():
            ok = build_package(pkg)
            if not ok:
                print(f"❌ Failed to build {pkg.name}", file=sys.stderr)
                success = False
            else:
                print(f"✅ Successfully built {pkg.name}\n")
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
