"""Structured JSON response formatter."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..types.response import SearchResponse


class JSONFormatter:
    """Format SearchResponse into clean dictionary or formatted JSON string."""

    def format(
        self,
        response: SearchResponse,
        as_string: bool = True,
        indent: int = 2,
        **kwargs: Any,
    ) -> str | dict[str, Any]:
        data = response.to_dict()
        if as_string:
            return json.dumps(data, indent=indent)
        return data
