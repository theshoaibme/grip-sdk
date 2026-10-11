"""Session store registry for multi-turn conversational histories."""

from __future__ import annotations

from typing import Any
from google_ai_search.core.session_store import (
    GoogleAISession,
    SessionStore as _BaseSessionStore,
)


class SessionStore(_BaseSessionStore):
    """SessionStore supporting both short and descriptive method names."""

    def create_session(
        self,
        title: str | None = None,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        engine: Any = None,
    ) -> GoogleAISession:
        return self.create(title=title, session_id=session_id, metadata=metadata, engine=engine)

    def get_session(self, session_id: str) -> GoogleAISession | None:
        return self.get(session_id)

    def delete_session(self, session_id: str) -> bool:
        return self.delete(session_id)

    def list(self) -> list[GoogleAISession]:
        with self._lock:
            return list(self._sessions.values())

    def list_sessions(self) -> list[GoogleAISession]:
        return self.list()

    def count(self) -> int:
        with self._lock:
            return len(self._sessions)

    def clear_all(self) -> int:
        return self.clear()


__all__ = ["GoogleAISession", "SessionStore"]
