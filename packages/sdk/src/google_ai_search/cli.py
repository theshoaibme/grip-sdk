"""Backward-compatibility re-export for main from cli."""

from .cli.main import main

__all__ = ["main"]

if __name__ == "__main__":
    main()
