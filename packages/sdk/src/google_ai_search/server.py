"""Backward-compatibility re-export for create_app from server."""

from .server.app import create_app

__all__ = ["create_app"]
