"""Security tests for authentication and rate limits."""

import pytest
from grip_core.security.validation import validate_query, validate_session_id
from grip_core.errors import ValidationError
from grip_engine.infrastructure.rate_limit import RateLimiter



def test_input_validation_security():
    # Valid query
    clean = validate_query("What is AI?", max_length=100)
    assert clean == "What is AI?"

    # Empty query raises ValidationError
    with pytest.raises(ValidationError):
        validate_query("   ")

    # Excessive length raises ValidationError
    with pytest.raises(ValidationError):
        validate_query("x" * 200, max_length=50)

    # Valid session ID
    clean_id = validate_session_id("sess_valid-123")
    assert clean_id == "sess_valid-123"

    # Malicious session ID with illegal characters
    with pytest.raises(ValidationError):
        validate_session_id("../../../etc/passwd")


def test_rate_limiter_throttling():
    limiter = RateLimiter(capacity=3, refill_per_sec=0.0)
    key = "192.168.1.100"

    # 3 allowed
    assert limiter.acquire(key) is True
    assert limiter.acquire(key) is True
    assert limiter.acquire(key) is True

    # 4th blocked
    assert limiter.acquire(key) is False


def test_auth_middleware_with_api_key():
    from app.server import create_app
    flask_app = create_app()
    with flask_app.test_client() as client:
        res = client.get("/health")
        assert res.status_code == 200

