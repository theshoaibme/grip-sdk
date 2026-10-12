"""Base tool definitions and tool registry for Google AI Search."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Tool:
    """A callable tool capability accessible to the agent or caller."""

    name: str
    description: str
    fn: Callable[..., Any]
    parameters_schema: dict[str, Any] = field(default_factory=dict)

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        return self.fn(*args, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters_schema,
        }


def _infer_schema(fn: Callable[..., Any]) -> dict[str, Any]:
    """Infer parameter schema from python type annotations and docstring."""
    try:
        sig = inspect.signature(fn)
        props: dict[str, Any] = {}
        required: list[str] = []
        for name, param in sig.parameters.items():
            if name in ("self", "cls"):
                continue
            param_type = "string"
            if param.annotation is int:
                param_type = "integer"
            elif param.annotation is float:
                param_type = "number"
            elif param.annotation is bool:
                param_type = "boolean"
            elif param.annotation in (list, tuple):
                param_type = "array"
            elif param.annotation is dict:
                param_type = "object"

            props[name] = {"type": param_type}
            if param.default is inspect.Parameter.empty:
                required.append(name)

        return {
            "type": "object",
            "properties": props,
            "required": required,
        }
    except Exception:
        return {"type": "object", "properties": {}}


class ToolRegistry:
    """Registry managing built-in and user-registered tools."""

    def __init__(self, load_builtins: bool = True) -> None:
        self._tools: dict[str, Tool] = {}
        if load_builtins:
            self.load_builtins()

    def register(
        self,
        name_or_fn: str | Callable[..., Any] | None = None,
        description: str | None = None,
        fn: Callable[..., Any] | None = None,
    ) -> Any:
        """Register a tool. Can be used as a decorator or direct method call.

        Usage:
            @client.tools.register(description="Calculate tax")
            def calc_tax(amount: float) -> float: ...

            # Or direct:
            client.tools.register("my_tool", "Description", my_fn)
        """
        if isinstance(name_or_fn, Tool):
            self._tools[name_or_fn.name] = name_or_fn
            return name_or_fn

        # Used as @register or @register()
        if callable(name_or_fn) and fn is None:
            actual_fn = name_or_fn
            tool_name = actual_fn.__name__
            tool_desc = description or actual_fn.__doc__ or f"Tool {tool_name}"
            schema = _infer_schema(actual_fn)
            tool = Tool(name=tool_name, description=tool_desc.strip(), fn=actual_fn, parameters_schema=schema)
            self._tools[tool_name] = tool
            return actual_fn

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = str(name_or_fn) if name_or_fn else func.__name__
            tool_desc = description or func.__doc__ or f"Tool {tool_name}"
            schema = _infer_schema(func)
            tool = Tool(name=tool_name, description=tool_desc.strip(), fn=func, parameters_schema=schema)
            self._tools[tool_name] = tool
            return func

        if fn is not None:
            tool_name = str(name_or_fn) if name_or_fn else fn.__name__
            tool_desc = description or fn.__doc__ or f"Tool {tool_name}"
            schema = _infer_schema(fn)
            tool = Tool(name=tool_name, description=tool_desc.strip(), fn=fn, parameters_schema=schema)
            self._tools[tool_name] = tool
            return tool

        return decorator

    def get(self, name: str) -> Tool | None:
        """Retrieve tool by name."""
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        """List all registered tools."""
        return list(self._tools.values())

    def names(self) -> list[str]:
        """Return names of registered tools."""
        return list(self._tools.keys())

    def __contains__(self, name: str) -> bool:
        """Check if tool name is registered."""
        return name in self._tools

    def call(self, name: str, *args: Any, **kwargs: Any) -> Any:
        """Execute a registered tool by name."""
        tool = self.get(name)
        if not tool:
            raise KeyError(f"Tool '{name}' is not registered.")
        return tool(*args, **kwargs)

    def load_builtins(self) -> None:
        """Register standard safe built-in tools."""
        from .builtin import (
            calculator,
            citation_verifier,
            create_pdf,
            json_extractor,
            page_fetcher,
            summarizer,
            unit_converter,
        )

        self.register(calculator)
        self.register(citation_verifier)
        self.register(page_fetcher)
        self.register(summarizer)
        self.register(json_extractor)
        self.register(unit_converter)
        self.register(create_pdf)

    def to_dict(self) -> list[dict[str, Any]]:
        return [t.to_dict() if hasattr(t, "to_dict") else t for t in self._tools.values()]
