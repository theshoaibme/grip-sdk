"""grip-engine: High-performance AI search orchestration engine with dynamic provider routing."""

from .engine import GripEngine
from .providers import (
    BaseSearchProvider,
    GoogleSearchProvider,
    OpenAISearchProvider,
    ProviderRegistry,
)
from .agent import (
    PlanExecutionResult,
    PlanStep,
    Rule,
    RulesRegistry,
    Skill,
    SkillsRegistry,
    StrictPlan,
    PlanManager,
    StrictPlanner,
    Workflow,
    WorkflowManager,
)
from .tools import (
    BaseTool,
    Tool,
    ToolRegistry,
    register_builtin_tools,
)
from .formatters import (
    BaseFormatter,
    CitationsFormatter,
    HtmlFormatter,
    JsonFormatter,
    MarkdownFormatter,
    TextFormatter,
)
from .infrastructure import (
    GoogleAISession,
    RateLimiter,
    SessionStore,
    TTLCache,
    TokenBucket,
)

__version__ = "0.3.0"

__all__ = [
    "GripEngine",
    "BaseSearchProvider",
    "GoogleSearchProvider",
    "OpenAISearchProvider",
    "ProviderRegistry",
    "Rule",
    "RulesRegistry",
    "Skill",
    "SkillsRegistry",
    "StrictPlan",
    "PlanManager",
    "StrictPlanner",
    "PlanStep",
    "PlanExecutionResult",
    "Workflow",
    "WorkflowManager",
    "BaseTool",
    "Tool",
    "ToolRegistry",
    "register_builtin_tools",
    "BaseFormatter",
    "JsonFormatter",
    "MarkdownFormatter",
    "TextFormatter",
    "HtmlFormatter",
    "CitationsFormatter",
    "TTLCache",
    "RateLimiter",
    "TokenBucket",
    "SessionStore",
    "GoogleAISession",
    "__version__",
]
