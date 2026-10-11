"""Input validation and sanitization for queries and inputs."""

from __future__ import annotations

import re
from typing import Any
from ..errors import ValidationError


def validate_query(query: Any, max_length: int = 4000) -> str:
    """Validate and clean a user search query."""
    if not isinstance(query, str) or not query.strip():
        raise ValidationError("Query must be a non-empty string.")

    clean = query.strip()
    if len(clean) > max_length:
        raise ValidationError(f"Query exceeds maximum allowed length of {max_length} characters.")

    return clean


def sanitize_session_id(session_id: str) -> str:
    """Ensure session IDs contain safe alphanumeric and hyphen characters."""
    clean = str(session_id).strip()
    if not re.match(r"^[a-zA-Z0-9_-]{1,64}$", clean):
        raise ValidationError(f"Invalid session ID format: '{clean}'")
    return clean


validate_session_id = sanitize_session_id

__all__ = ["validate_query", "sanitize_session_id", "validate_session_id"]
