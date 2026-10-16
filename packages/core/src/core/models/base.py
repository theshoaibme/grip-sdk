"""Base model mixins and utilities."""

from __future__ import annotations

from typing import Any


class DictAccessMixin:
    """Production-grade dictionary access mixin for dataclasses.

    Enables both attribute access (obj.attr) and dictionary-style access
    (obj["attr"], obj.get("attr"), "attr" in obj).
    """

    def __getitem__(self, key: str) -> Any:
        try:
            return getattr(self, key)
        except AttributeError:
            raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def __contains__(self, key: str) -> bool:
        return hasattr(self, key)

    def keys(self) -> list[str]:
        if hasattr(self, "__dataclass_fields__"):
            return list(self.__dataclass_fields__.keys())
        return [k for k in self.__dict__.keys() if not k.startswith("_")]

    def items(self) -> list[tuple[str, Any]]:
        return [(k, getattr(self, k)) for k in self.keys()]

    def values(self) -> list[Any]:
        return [getattr(self, k) for k in self.keys()]
