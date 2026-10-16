#!/usr/bin/env python3
"""Basic AI Search example using the Grip SDK.

https://grip.theshoaib.me/
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in [
    _ROOT / "packages" / "sdk" / "src",
    _ROOT / "packages" / "core" / "src",
    _ROOT / "packages" / "engine" / "src",
    _ROOT,
]:
    _s = str(_p)
    if _p.exists() and _s not in sys.path:
        sys.path.insert(0, _s)

from grip import Grip



def main():
    print("✨ Grip SDK: Synchronous Search Example\n")

    # Initialize client (uses embedded engine or connects to GRIP_API_URL if set)
    client = Grip()

    query = "Latest developments in humanoid robotics"
    print(f"Querying: '{query}'...\n")

    try:
        response = client.search.query(query)
        print("=== Answer ===")
        print(response.answer)
        print("\n=== Grounded Sources ===")
        for s in response.sources:
            print(f"- {s.title}: {s.link or s.url}")

        if response.thinking:
            print("\n=== Model Reasoning ===")
            print(response.thinking)

    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
