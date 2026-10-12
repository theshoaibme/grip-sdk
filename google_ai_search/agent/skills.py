"""Skills registry for defining and composing domain capabilities."""

from __future__ import annotations

from typing import Any

from ..types.agent import Skill


class SkillsRegistry:
    """Registry maintaining domain skills, specialized prompt instructions, and tool sets."""

    def __init__(self) -> None:
        self._skills: dict[str, Skill] = {}

    def register(
        self,
        name: str,
        description: str,
        instructions: str,
        tools: list[str] | None = None,
        examples: list[dict[str, str]] | None = None,
    ) -> Skill:
        """Register a new domain capability skill.

        Usage:
            client.skills.register(
                name="academic_researcher",
                description="Performs high-rigor scientific literature synthesis",
                instructions="Focus on peer-reviewed methodology and statistical significance.",
                tools=["citation_verifier", "page_fetcher"],
            )
        """
        skill = Skill(
            name=name.strip().lower(),
            description=description.strip(),
            instructions=instructions.strip(),
            tools=tools or [],
            examples=examples or [],
        )
        self._skills[skill.name] = skill
        return skill

    def get(self, name: str) -> Skill | None:
        """Retrieve a skill by name."""
        return self._skills.get(name.strip().lower())

    def list(self) -> list[Skill]:
        """List all registered skills."""
        return list(self._skills.values())

    def delete(self, name: str) -> bool:
        """Delete a skill by name."""
        return self._skills.pop(name.strip().lower(), None) is not None

    def compile(self, skill_names: list[str] | None = None) -> str:
        """Compile selected (or all) skills into prompt context."""
        target_skills = (
            [self._skills[k] for k in skill_names if k in self._skills]
            if skill_names is not None
            else list(self._skills.values())
        )
        if not target_skills:
            return ""

        sections = ["[ACTIVE SKILLS & INSTRUCTIONS]"]
        for s in target_skills:
            sections.append(f"### Skill: {s.name}\n{s.description}\n{s.instructions}")
            if s.tools:
                sections.append(f"Tools available: {', '.join(s.tools)}")
        return "\n\n".join(sections)

    def clear(self) -> int:
        """Clear all registered skills."""
        count = len(self._skills)
        self._skills.clear()
        return count

    def count(self) -> int:
        return len(self._skills)

    def to_dict(self) -> list[dict[str, Any]]:
        return [s.to_dict() if hasattr(s, "to_dict") else s for s in self._skills.values()]
