"""Agent domain models: Rules, Skills, Strict Plans, and Workflows."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Rule:
    """A behavioral, formatting, or negative constraint directive."""

    name: str
    content: str
    priority: int = 1
    active: bool = True
    role: str = "user"  # "user" (high priority) | "system"

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "content": self.content,
            "priority": self.priority,
            "active": self.active,
            "role": self.role,
        }


@dataclass
class Skill:
    """A specialized instruction set and domain capability."""

    name: str
    description: str
    instructions: str
    tools: list[str] = field(default_factory=list)
    examples: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": self.tools,
            "examples": self.examples,
        }


@dataclass
class PlanStep:
    """A discrete unit of work within a strict execution plan."""

    step_number: int
    instruction: str
    status: str = "pending"  # "pending" | "in_progress" | "completed" | "failed" | "skipped"
    result: Any = None
    thinking: str | None = None
    error: str | None = None
    started_at: float | None = None
    completed_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "step_number": self.step_number,
            "instruction": self.instruction,
            "status": self.status,
        }
        if self.result is not None:
            d["result"] = self.result if not hasattr(self.result, "to_dict") else self.result.to_dict()
        if self.thinking:
            d["thinking"] = self.thinking
        if self.error:
            d["error"] = self.error
        if self.started_at is not None:
            d["started_at"] = round(self.started_at, 3)
        if self.completed_at is not None:
            d["completed_at"] = round(self.completed_at, 3)
        return d


@dataclass
class PlanExecutionResult:
    """Summary result of an executed strict plan."""

    goal: str
    steps: list[PlanStep] = field(default_factory=list)
    status: str = "completed"  # "completed" | "failed"
    summary: str = ""
    duration_sec: float = 0.0

    @property
    def success(self) -> bool:
        return self.status == "completed"

    @property
    def completed_steps(self) -> int:
        return sum(1 for s in self.steps if s.status == "completed")

    @property
    def step_results(self) -> list[Any]:
        return [s.result for s in self.steps]

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status,
            "success": self.success,
            "summary": self.summary,
            "duration_sec": round(self.duration_sec, 3),
            "step_count": len(self.steps),
            "completed_steps": self.completed_steps,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class WorkflowStep:
    """A configured pipeline step within an automated workflow."""

    name: str
    action: str  # "search" | "tool" | "format" | "custom"
    params: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "action": self.action,
            "params": self.params,
        }


@dataclass
class WorkflowResult:
    """Result emitted after executing a workflow pipeline."""

    workflow_name: str
    success: bool = True
    steps_completed: int = 0
    output: Any = None
    step_outputs: dict[str, Any] = field(default_factory=dict)
    duration_sec: float = 0.0

    @property
    def results(self) -> dict[str, Any]:
        return self.step_outputs

    def to_dict(self) -> dict[str, Any]:
        out = self.output if not hasattr(self.output, "to_dict") else self.output.to_dict()
        return {
            "workflow_name": self.workflow_name,
            "success": self.success,
            "steps_completed": self.steps_completed,
            "output": out,
            "step_outputs": {k: v if not hasattr(v, "to_dict") else v.to_dict() for k, v in self.step_outputs.items()},
            "results": {k: v if not hasattr(v, "to_dict") else v.to_dict() for k, v in self.step_outputs.items()},
            "duration_sec": round(self.duration_sec, 3),
        }
