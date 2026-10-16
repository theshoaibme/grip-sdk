"""Rules registry for maintaining behavioral and negative constraints, system identity, and response format."""

from __future__ import annotations

import uuid
from typing import Any

from ..prompts import get_response_format, get_system_identity
from ..types.agent import Rule


class RulesRegistry:
    """Registry maintaining behavioral guidelines, style constraints, system identity, and response format."""

    def __init__(self) -> None:
        self._rules: dict[str, Rule] = {}
        self._identity: str | None = None
        # Universal response format assigned for all by default (loaded from markdown)
        self._response_format: str | None = get_response_format()

    @property
    def identity(self) -> str | None:
        """System identity / persona directive."""
        return self._identity or get_system_identity()

    @identity.setter
    def identity(self, value: str | None) -> None:
        self.set_identity(value)

    def set_identity(self, identity: str | None) -> None:
        """Set the system identity and persona directive."""
        self._identity = str(identity).strip() if identity else None

    def get_identity(self) -> str | None:
        """Get the current system identity directive."""
        return self.identity

    @property
    def response_format(self) -> str | None:
        """Response format directive."""
        return self._response_format or get_response_format()

    @response_format.setter
    def response_format(self, value: str | None) -> None:
        self.set_response_format(value)

    def set_response_format(self, response_format: str | None) -> None:
        """Set the response formatting specification."""
        self._response_format = str(response_format).strip() if response_format else None

    def get_response_format(self) -> str | None:
        """Get the current response format directive."""
        return self.response_format

    def add(
        self,
        rule_or_content: str | Rule | None = None,
        name: str | None = None,
        priority: int = 1,
        *,
        content: str | None = None,
        role: str = "user",
        active: bool = True,
    ) -> Rule:
        """Add a behavioral rule or negative constraint. All user role rules have highest priority.

        Usage:
            client.rules.add("Always cite primary scientific sources")
            client.rules.add(content="Output strictly in lowercase", name="lowercase_only", priority=1)
        """
        actual_content = content if content is not None else (rule_or_content if isinstance(rule_or_content, str) else None)
        if isinstance(rule_or_content, Rule):
            rule = rule_or_content
        elif actual_content is not None:
            rule_name = name or f"rule_{uuid.uuid4().hex[:8]}"
            rule = Rule(
                name=rule_name,
                content=str(actual_content).strip(),
                priority=priority,
                active=active,
                role=role,
            )
        else:
            raise ValueError("Rule content must be provided.")

        self._rules[rule.name] = rule
        return rule

    def toggle(self, name: str, active: bool | None = None) -> Rule | None:
        """Toggle or set the active status of a rule."""
        rule = self._rules.get(name)
        if not rule:
            return None
        rule.active = not rule.active if active is None else bool(active)
        return rule

    def update(
        self,
        name: str,
        content: str | None = None,
        priority: int | None = None,
        active: bool | None = None,
        role: str | None = None,
    ) -> Rule | None:
        """Update an existing rule."""
        rule = self._rules.get(name)
        if not rule:
            return None
        if content is not None:
            rule.content = str(content).strip()
        if priority is not None:
            rule.priority = int(priority)
        if active is not None:
            rule.active = bool(active)
        if role is not None:
            rule.role = str(role).strip()
        return rule

    def remove(self, name: str) -> bool:
        """Remove a rule by name."""
        return self._rules.pop(name, None) is not None

    def get(self, name: str) -> Rule | None:
        """Retrieve a rule by name."""
        return self._rules.get(name)

    def list(self, active_only: bool = True, enabled_only: bool | None = None) -> list[Rule]:
        """List rules with all user role rules receiving top priority, sorted by priority ascending."""
        only = active_only if enabled_only is None else enabled_only
        rules = [r for r in self._rules.values() if not only or r.active]
        # User roles have highest priority (precedence 0 vs 1), then sorted by priority ascending
        return sorted(rules, key=lambda r: (0 if getattr(r, "role", "user") == "user" else 1, r.priority))

    def compile(self) -> str:
        """Compile system identity, universal response format, and active rules into structured prompt directives."""
        sections: list[str] = []

        identity = self.identity
        if identity and identity.strip():
            sections.append(f"[SYSTEM IDENTITY]\n{identity.strip()}")

        resp_format = self.response_format
        if resp_format and resp_format.strip():
            sections.append(f"[RESPONSE FORMAT INSTRUCTIONS]\n{resp_format.strip()}")

        active_rules = self.list(active_only=True)
        if active_rules:
            lines = ["[STRICT BEHAVIORAL RULES]"]
            for idx, r in enumerate(active_rules, start=1):
                lines.append(f"{idx}. {r.content}")
            sections.append("\n".join(lines))

        return "\n\n".join(sections)

    def clear(self) -> int:
        """Clear all registered rules."""
        count = len(self._rules)
        self._rules.clear()
        return count

    def reset(self) -> None:
        """Reset all rules, system identity, and restore default response format."""
        self._rules.clear()
        self._identity = None
        self._response_format = get_response_format()

    def count(self) -> int:
        return len(self._rules)

    def to_dict(self) -> list[dict[str, Any]]:
        return [r.to_dict() if hasattr(r, "to_dict") else r for r in self.list(active_only=False)]

    def to_config_dict(self) -> dict[str, Any]:
        """Full system rules configuration dictionary."""
        return {
            "identity": self.identity or "",
            "response_format": self.response_format or "",
            "rules": [r.to_dict() if hasattr(r, "to_dict") else r for r in self.list(active_only=False)],
            "compiled": self.compile(),
            "total": len(self._rules),
            "active_count": len(self.list(active_only=True)),
        }
