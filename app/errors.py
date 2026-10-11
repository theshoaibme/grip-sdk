"""Re-export error utilities from google_ai_search.errors."""

from google_ai_search.errors import error_response, register_error_handlers

__all__ = ["error_response", "register_error_handlers"]
