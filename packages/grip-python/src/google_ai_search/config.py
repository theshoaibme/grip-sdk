"""Configuration management for Google AI Browser Mode."""

import os
from dataclasses import dataclass, field
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass



def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer, got {raw!r}") from exc


def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Config:
    """Runtime configuration for Google AI Search Browser Mode."""

    answer_provider: str = "google_ai"

    # Browser automation settings for Google AI Mode (udm=50)
    browser_headless: bool = field(
        default_factory=lambda: _get_bool("BROWSER_HEADLESS", True)
    )
    browser_user_data_dir: str = field(
        default_factory=lambda: os.getenv("BROWSER_USER_DATA_DIR", ".chrome-profile")
    )
    browser_channel: str = field(
        default_factory=lambda: os.getenv("BROWSER_CHANNEL", "chrome")
    )
    browser_timeout: int = field(
        default_factory=lambda: _get_int("BROWSER_TIMEOUT", 60)
    )
    browser_lang: str = field(
        default_factory=lambda: os.getenv("BROWSER_LANG", "en")
    )
    browser_gl: str = field(
        default_factory=lambda: os.getenv("BROWSER_GL", "")
    )
    user_agent_override: str = field(
        default_factory=lambda: os.getenv("USER_AGENT_OVERRIDE", "")
    )

    # Proxy settings
    proxy_server: str = field(
        default_factory=lambda: os.getenv("PROXY_SERVER", os.getenv("PROXY_URL", ""))
    )
    proxy_username: str = field(
        default_factory=lambda: os.getenv("PROXY_USERNAME", "")
    )
    proxy_password: str = field(
        default_factory=lambda: os.getenv("PROXY_PASSWORD", "")
    )

    # Anti-bot and fallback behavior
    fallback_on_block: bool = field(
        default_factory=lambda: _get_bool("FALLBACK_ON_BLOCK", True)
    )

    # Sessions
    session_ttl_sec: int = field(
        default_factory=lambda: _get_int("SESSION_TTL_SEC", 3600)
    )

    # General network and limits
    request_timeout: int = field(
        default_factory=lambda: _get_int("REQUEST_TIMEOUT", 15)
    )
    rate_limit_capacity: int = field(
        default_factory=lambda: _get_int("RATE_LIMIT_CAPACITY", 30)
    )
    rate_limit_refill_per_sec: int = field(
        default_factory=lambda: _get_int("RATE_LIMIT_REFILL_PER_SEC", 1)
    )
    cache_ttl: int = field(
        default_factory=lambda: _get_int("CACHE_TTL", 300)
    )
    cache_max_entries: int = field(
        default_factory=lambda: _get_int("CACHE_MAX_ENTRIES", 500)
    )
    stream_delay_ms: int = field(
        default_factory=lambda: _get_int("STREAM_DELAY_MS", 20)
    )
    port: int = field(
        default_factory=lambda: _get_int("PORT", 8000)
    )
    debug: bool = field(
        default_factory=lambda: os.getenv("FLASK_DEBUG", "0") == "1"
    )

    # Compatibility
    max_results: int = 10
    search_provider: str = "google_ai"

    def require_credentials(self) -> None:
        """No API keys required for Google AI Browser Mode."""
        pass


_default_config: Config | None = None


def get_config() -> Config:
    global _default_config
    if _default_config is None:
        _default_config = Config()
    return _default_config
