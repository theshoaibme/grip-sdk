#!/usr/bin/env python3
"""Pre-release verification script for Grip Platform."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_tests() -> bool:
    print("🧪 Running full test suite...")
    cmd = [sys.executable, "-m", "pytest", "tests/"]
    result = subprocess.run(cmd, cwd=ROOT)
    return result.returncode == 0


def check_imports() -> bool:
    print("🔍 Checking package imports and provider registrations...")
    try:
        import grip
        import grip_core
        import grip_engine
        from grip_engine.providers.registry import default_provider_registry

        providers = default_provider_registry.list_providers()
        print(f"  ✓ grip SDK v{grip.__version__} loaded")
        print(f"  ✓ Available search providers: {providers}")
        return True
    except Exception as exc:
        print(f"  ❌ Import error: {exc}", file=sys.stderr)
        return False


def main() -> int:
    print("🚀 Grip Platform Release Health Check\n")
    if not check_imports():
        return 1
    if not check_tests():
        return 1
    print("\n🎉 All release checks passed successfully!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
