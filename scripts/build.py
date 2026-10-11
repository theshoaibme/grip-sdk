#!/usr/bin/env python3
"""Build script for Grip Platform packages."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PACKAGES = [
    ROOT / "packages" / "grip-core",
    ROOT / "packages" / "grip-python",
    ROOT / "engine",
]


def build_package(pkg_path: Path) -> bool:
    print(f"📦 Building package in {pkg_path.relative_to(ROOT)}...")
    cmd = [sys.executable, "-m", "build", "--wheel", "--sdist", str(pkg_path)]
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode == 0


def main() -> int:
    print("🚀 Starting Grip Platform Build Pipeline\n")
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
