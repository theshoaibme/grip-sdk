"""Tests for Grip SDK resources."""

from unittest.mock import MagicMock
import pytest

from grip import Grip, SearchResponse, SourceItem
from grip.resources.search import SearchResource
from grip.resources.sessions import SessionsResource


def test_search_resource_callable():
    mock_client = MagicMock()
    mock_client._execute_query.return_value = SearchResponse(
        answer="Callable answer", sources=[], query="test"
    )
    res_mgr = SearchResource(mock_client)
    res = res_mgr("test", provider="google")
    assert res.answer == "Callable answer"
    mock_client._execute_query.assert_called_with(
        query="test",
        session_id=None,
        provider="google",
        thread_id=None,
        timeout=None,
    )


def test_sessions_resource_operations():
    mock_client = MagicMock()
    mock_client._create_session.return_value = MagicMock(session_id="s1")
    mock_client._list_sessions.return_value = []
    mock_client._delete_session.return_value = True

    sess_mgr = SessionsResource(mock_client)
    s = sess_mgr.create(title="My Title")
    assert s.session_id == "s1"
    assert sess_mgr.list() == []
    assert sess_mgr.delete("s1") is True
