"""Environment configuration re-exporting from google_ai_search."""

from google_ai_search.config import Config, ConfigError, get_config

config = get_config()

__all__ = ["Config", "ConfigError", "config", "get_config"]
