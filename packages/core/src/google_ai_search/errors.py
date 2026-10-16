"""HTTP error response helpers and error handlers."""

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException


def error_response(message: str, status: int = 400, **extra):
    """Build a standard JSON error response."""
    payload = {"error": message, "status": status}
    payload.update(extra)
    response = jsonify(payload)
    response.status_code = status
    if "retry_after" in extra and extra["retry_after"] is not None:
        response.headers["Retry-After"] = str(extra["retry_after"])
    return response


def register_error_handlers(app: Flask) -> None:
    """Register standard error handlers on the Flask app."""

    @app.errorhandler(HTTPException)
    def handle_http_error(exc: HTTPException):
        return error_response(exc.description or exc.name, exc.code or 500)

    @app.errorhandler(Exception)
    def handle_unexpected(exc: Exception):  # pragma: no cover - safety net
        app.logger.exception("Unhandled error: %s", exc)
        return error_response("Internal server error", 500)
