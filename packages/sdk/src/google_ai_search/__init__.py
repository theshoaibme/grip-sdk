"""Google AI Search Python SDK.

A modern, pythonic SDK for interacting with Google AI Search (udm=50 / AI Mode),
extracting AI-generated overviews, grounded web source citations, real-time token
streaming, multi-turn conversational input sessions, skills, rules, workflows,
strict planning, and built-in tools via browser automation.

Basic usage:
    >>> import google_ai_search as gas
    >>> client = gas.GoogleAI()

    # Search query with citations and thinking
    >>> response = client.search.query("Why is the sky blue?")
    >>> print(response.answer)
    >>> print(response.to_markdown())

    # Rules
    >>> client.rules.add("Always cite primary scientific sources")

    # Skills
    >>> client.skills.register("research", "Literature review", "Focus on PubMed/arXiv")

    # Built-in tools
    >>> result = client.tools.call("calculator", expression="2**16 - 1")

    # Strict planning
    >>> plan = client.plan.create("Analyze fusion milestones", ["Search 2026 milestones"])
    >>> plan_result = plan.execute(client)
"""

from ._version import __version__
from .agent import (
    PlanManager,
    RulesRegistry,
    SkillsRegistry,
    StrictPlan,
    Workflow,
    WorkflowManager,
)
from .client import GoogleAI, GoogleAISearch, GoogleAISearchClient
from .config import Config, get_config
from .core.engine import GoogleAIModeEngine, clear_profile_cookies
from .core.session_store import GoogleAISession, SessionManager, SessionStore
from .exceptions import (
    BotBlockedError,
    ConfigError,
    GoogleAISearchError,
    ProviderError,
    QuotaExceededError,
    SessionNotFoundError,
)
from .formatters import FormatterRegistry, format_response
from .resources.search import SearchResource
from .resources.sessions import SessionsResource
from .server.app import create_app
from .tools import (
    Tool,
    ToolRegistry,
    calculator,
    citation_verifier,
    json_extractor,
    page_fetcher,
    summarizer,
    unit_converter,
)
from .types import (
    PlanExecutionResult,
    PlanStep,
    Rule,
    SearchResponse,
    SessionDetail,
    SessionMessage,
    SessionSummary,
    Skill,
    SourceItem,
    StreamChunk,
    WorkflowResult,
    WorkflowStep,
)

__all__ = [
    "GoogleAI",
    "GoogleAISearch",
    "GoogleAISearchClient",
    "SearchResource",
    "SessionsResource",
    "GoogleAIModeEngine",
    "clear_profile_cookies",
    "GoogleAISession",
    "SessionStore",
    "SessionManager",
    "SearchResponse",
    "StreamChunk",
    "SourceItem",
    "SessionMessage",
    "SessionSummary",
    "SessionDetail",
    "Rule",
    "Skill",
    "PlanStep",
    "PlanExecutionResult",
    "WorkflowStep",
    "WorkflowResult",
    "RulesRegistry",
    "SkillsRegistry",
    "StrictPlan",
    "PlanManager",
    "Workflow",
    "WorkflowManager",
    "Tool",
    "ToolRegistry",
    "calculator",
    "citation_verifier",
    "page_fetcher",
    "summarizer",
    "json_extractor",
    "unit_converter",
    "FormatterRegistry",
    "format_response",
    "GoogleAISearchError",
    "BotBlockedError",
    "SessionNotFoundError",
    "ProviderError",
    "QuotaExceededError",
    "ConfigError",
    "Config",
    "get_config",
    "create_app",
    "__version__",
]
