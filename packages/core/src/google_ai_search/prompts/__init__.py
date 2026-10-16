"""Centralized prompt templates and loaders for Grip SDK and Google AI Search."""

from __future__ import annotations

import functools
from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent


@functools.lru_cache(maxsize=32)
def load_prompt(name: str, fallback: str = "") -> str:
    """Load a prompt markdown file from the prompts directory with optional fallback."""
    clean_name = name if name.endswith(".md") else f"{name}.md"
    target_file = _PROMPTS_DIR / clean_name
    try:
        if target_file.is_file():
            return target_file.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return fallback.strip()


def get_system_identity() -> str:
    """Get standard system identity directive."""
    return load_prompt(
        "system_identity",
        fallback="You are an intelligent, autonomous AI assistant equipped with real-time web search, document generation, and multi-provider reasoning capabilities.",
    )


def get_response_format() -> str:
    """Get universal response formatting directive assigned to all agents and searches."""
    return load_prompt(
        "response_format",
        fallback=(
            "Format all responses cleanly, directly, and professionally:\n"
            "- Deliver immediate, direct, and authoritative answers with zero conversational fluff, robotic preamble, or repetitive introductions.\n"
            "- Organize complex information using clear Markdown headers (`###`), concise bullet points, and high-density explanations.\n"
            "- When generating code, always output self-contained, complete code snippets inside fenced code blocks with appropriate language tags.\n"
            "- Ground factual and technical claims with precise citations and verified web references when available.\n"
            "- Maintain an objective, accurate, and helpful tone across all interactions."
        ),
    )


def get_system_rules() -> str:
    """Get core system behavioral rules."""
    return load_prompt(
        "system_rules",
        fallback=(
            "- Factuality & Verification: Prioritize verified facts, primary documentation, and live search results over speculative claims.\n"
            "- Safety & Integrity: Strictly refuse malicious actions, exploit payload generation, or unauthorized financial, medical, or legal advice.\n"
            "- Clarity & Structure: Present explanations with clean Markdown headers, bullet points, and syntax-highlighted code blocks.\n"
            "- Provider Uniformity: Adhere strictly to user constraints and behavioral directives regardless of backend model."
        ),
    )


def get_capabilities() -> str:
    """Get standard AI assistant capabilities description."""
    return load_prompt(
        "capabilities",
        fallback=(
            "I can assist you with a wide range of tasks:\n\n"
            "- **Answering Questions**: Clear explanations across technology, science, business, and everyday topics.\n"
            "- **Live Web Search**: Grounded information with real-time web references and sources.\n"
            "- **Code & Development**: Writing, debugging, explaining, and refactoring code in multiple languages.\n"
            "- **Analysis & Writing**: Summarizing articles, drafting documents, brainstorming, and structuring plans.\n\n"
            "What would you like to work on?"
        ),
    )


def get_agent_reasoning() -> str:
    """Get ReAct reasoning prompt template for autonomous agent execution."""
    return load_prompt(
        "agent_reasoning",
        fallback=(
            "Format your reasoning in these steps:\n"
            "Thought: <your reasoning>\n"
            "Action: <tool_name>\n"
            "Action Input: <json_formatted_tool_arguments>\n"
            "Or when finished:\n"
            "Final Answer: <your final comprehensive response>"
        ),
    )


def get_identity(provider: str | None = None) -> str:
    """Get dynamic identity introduction based on provider from markdown prompts."""
    prov = (provider or "").lower()
    if "chatgpt" in prov:
        return load_prompt("identity_chatgpt")
    if "gemini" in prov:
        return load_prompt("identity_gemini")
    if "openai" in prov:
        return load_prompt("identity_openai", fallback=load_prompt("identity_chatgpt"))
    return load_prompt("identity_grip")


def get_greeting() -> str:
    """Get standard warm greeting from markdown prompt."""
    return load_prompt("greetings", fallback="Hello! How can I help you today?")


def get_wellbeing() -> str:
    """Get wellbeing conversational response from markdown prompt."""
    return load_prompt("wellbeing", fallback="I'm doing well, thank you for asking! How can I help you today?")


def get_gratitude() -> str:
    """Get gratitude conversational response from markdown prompt."""
    return load_prompt("gratitude", fallback="You're welcome! Let me know if you need anything else.")


def get_farewell() -> str:
    """Get farewell conversational response from markdown prompt."""
    return load_prompt("farewells", fallback="Goodbye! Have a great day, and feel free to reach out whenever you need assistance.")


def get_acknowledgement() -> str:
    """Get conversational acknowledgement from markdown prompt."""
    return load_prompt("acknowledgements", fallback="Glad to help! Let me know what you'd like to explore next.")


__all__ = [
    "load_prompt",
    "get_system_identity",
    "get_response_format",
    "get_system_rules",
    "get_capabilities",
    "get_agent_reasoning",
    "get_identity",
    "get_greeting",
    "get_wellbeing",
    "get_gratitude",
    "get_farewell",
    "get_acknowledgement",
]
