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
            extra = getattr(self, "extra", None)
            if isinstance(extra, dict) and key in extra:
                return extra[key]
            raise KeyError(key)

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def get(self, key: str, default: Any = None) -> Any:
        if hasattr(self, key):
            val = getattr(self, key)
            if val is not None:
                return val
        extra = getattr(self, "extra", None)
        if isinstance(extra, dict) and key in extra:
            return extra[key]
        return default

    def __contains__(self, key: str) -> bool:
        if hasattr(self, key):
            return True
        extra = getattr(self, "extra", None)
        return isinstance(extra, dict) and key in extra

    def keys(self) -> list[str]:
        if hasattr(self, "__dataclass_fields__"):
            base_keys = list(self.__dataclass_fields__.keys())
        else:
            base_keys = [k for k in self.__dict__.keys() if not k.startswith("_")]
        extra = getattr(self, "extra", None)
        if isinstance(extra, dict):
            for k in extra.keys():
                if k not in base_keys:
                    base_keys.append(k)
        return base_keys

    def items(self) -> list[tuple[str, Any]]:
        return [(k, self[k]) for k in self.keys()]

    def values(self) -> list[Any]:
        return [self[k] for k in self.keys()]
