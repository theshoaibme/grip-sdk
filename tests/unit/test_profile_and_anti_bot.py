"""Unit tests for Chrome profile detection, User-Agent extraction, and low latency caching."""

import os
import time
from unittest.mock import MagicMock
from google_ai_search.core.profile import (
    detect_system_chrome_profile,
    detect_system_chrome_version,
    extract_client_user_agent,
    get_anti_detection_client_hints,
    get_chrome_profile,
    is_profile_locked,
)
from grip import Grip
from grip_core.models.response import SearchResponse


def test_detect_system_chrome_version():
    ver = detect_system_chrome_version()
    assert isinstance(ver, str)
    assert len(ver.split(".")) >= 2


def test_extract_client_user_agent():
    # 1. Real browser user agent
    real_ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    req_mock = MagicMock()
    req_mock.headers = {"User-Agent": real_ua}
    assert extract_client_user_agent(req_mock) == real_ua

    # 2. Dict headers
    assert extract_client_user_agent({"User-Agent": real_ua}) == real_ua

    # 3. Fallback when request is from curl / python-requests
    python_ua = "python-requests/2.31.0"
    extracted = extract_client_user_agent({"User-Agent": python_ua})
    assert "Mozilla/5.0" in extracted
    assert "Chrome/" in extracted


def test_get_anti_detection_client_hints():
    hints = get_anti_detection_client_hints()
    assert "Sec-Ch-Ua" in hints
    assert "Sec-Ch-Ua-Mobile" in hints
    assert "Sec-Ch-Ua-Platform" in hints
    assert hints["Sec-Ch-Ua-Mobile"] == "?0"


def test_get_chrome_profile_and_lock_handling(tmp_path):
    # Create mock profile directory with a lockfile
    mock_profile = tmp_path / "google-chrome-test"
    mock_profile.mkdir()
    (mock_profile / "SingletonLock").write_text("1234")
    (mock_profile / "Local State").write_text('{"browser": {}}')
    default_dir = mock_profile / "Default"
    default_dir.mkdir()
    (default_dir / "Preferences").write_text('{"profile": {}}')

    assert is_profile_locked(str(mock_profile)) is True

    # Resolving with copy_if_locked safely produces a clone
    dest_clone = tmp_path / "cloned-profile"
    resolved = get_chrome_profile(
        target_dir=str(mock_profile),
        copy_if_locked=True,
        clone_destination=str(dest_clone),
    )
    assert resolved == str(dest_clone)
    assert os.path.exists(os.path.join(resolved, "Local State"))
    assert os.path.exists(os.path.join(resolved, "Default", "Preferences"))
    assert not os.path.exists(os.path.join(resolved, "SingletonLock"))


def test_ultra_low_latency_caching():
    mock_engine = MagicMock()
    mock_engine.search.return_value = SearchResponse(
        answer="Quantum information science",
        sources=[],
        query="what is quantum computing",
        status="success",
    )

    client = Grip(engine=mock_engine, cache=True)

    # 1st call -> engine is called
    t0 = time.time()
    res1 = client.search.query("what is quantum computing")
    duration1 = time.time() - t0
    assert mock_engine.search.call_count == 1
    assert res1.answer == "Quantum information science"

    # 2nd call -> served from cache with almost zero latency (<1ms)
    t1 = time.time()
    res2 = client.search.query("what is quantum computing")
    duration2 = time.time() - t1
    assert mock_engine.search.call_count == 1  # Not called again
    assert res2.cached is True
    assert duration2 < 0.005  # < 5ms (typically 0.0002s)


def test_client_custom_user_agent_propagation():
    mock_engine = MagicMock()
    mock_engine.search.return_value = SearchResponse(
        answer="OK",
        sources=[],
        query="test query",
    )
    custom_ua = "Mozilla/5.0 (CustomBrowser/1.0)"
    client = Grip(engine=mock_engine, user_agent=custom_ua)

    client.search.query("test query")
    mock_engine.search.assert_called_with(
        query="test query",
        session_id=None,
        provider="google",
        thread_id=None,
        user_agent=custom_ua,
    )
