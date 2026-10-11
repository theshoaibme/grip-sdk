"""CLI delegator pointing to grip.cli."""

from __future__ import annotations

import sys
from grip.cli import main

if __name__ == "__main__":
    sys.exit(main())
