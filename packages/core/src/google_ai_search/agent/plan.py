"""Strict Plan engine for goal-oriented multi-step execution."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any

from ..types.agent import PlanExecutionResult, PlanStep

if TYPE_CHECKING:
    from ..client import GoogleAI


class StrictPlan:
    """A goal-oriented, strictly ordered multi-step plan."""

    def __init__(
        self,
        goal: str,
        steps: list[str | PlanStep] | None = None,
        strict_order: bool = True,
        abort_on_failure: bool = True,
    ) -> None:
        self.goal = goal
        self.strict_order = strict_order
        self.abort_on_failure = abort_on_failure
        self.status = "pending"
        self.steps: list[PlanStep] = []

        if steps:
            for s in steps:
                if isinstance(s, PlanStep):
                    self.steps.append(s)
                else:
                    self.add_step(str(s))

    def add_step(self, instruction: str) -> PlanStep:
        """Add a step to the plan."""
        step_num = len(self.steps) + 1
        step = PlanStep(step_number=step_num, instruction=instruction.strip())
        self.steps.append(step)
        return step

    def execute(self, client: GoogleAI) -> PlanExecutionResult:
        """Strictly execute all steps in order through the GoogleAI client."""
        start_time = time.time()
        self.status = "in_progress"
        all_success = True

        for idx, step in enumerate(self.steps):
            step.status = "in_progress"
            step.started_at = time.time()

            try:
                step.thinking = f"Executing step {step.step_number}/{len(self.steps)}: {step.instruction}"

                # Check if instruction is a math expression or tool invocation
                handled_by_tool = False
                if hasattr(client, "tools") and client.tools:
                    # If instruction starts with calculator: or matches math
                    if step.instruction.startswith("calc:") or step.instruction.startswith("math:"):
                        expr = step.instruction.split(":", 1)[1].strip()
                        calc_res = client.tools.call("calculator", expression=expr)
                        step.result = {"answer": str(calc_res), "tool": "calculator"}
                        handled_by_tool = True

                if not handled_by_tool:
                    # Execute search with client
                    resp = client.search.query(step.instruction)
                    step.result = resp
                    if getattr(resp, "thinking", None):
                        step.thinking = resp.thinking

                step.status = "completed"
                step.completed_at = time.time()

            except Exception as exc:
                all_success = False
                step.status = "failed"
                step.error = str(exc)
                step.completed_at = time.time()

                if self.abort_on_failure:
                    # Skip subsequent steps
                    for remaining in self.steps[idx + 1 :]:
                        remaining.status = "skipped"
                    break

        self.status = "completed" if all_success else "failed"
        duration = time.time() - start_time

        completed_count = sum(1 for s in self.steps if s.status == "completed")
        summary = f"Plan '{self.goal}': {completed_count}/{len(self.steps)} steps completed in {duration:.2f}s."

        return PlanExecutionResult(
            goal=self.goal,
            steps=list(self.steps),
            status=self.status,
            summary=summary,
            duration_sec=duration,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "status": self.status,
            "strict_order": self.strict_order,
            "abort_on_failure": self.abort_on_failure,
            "steps": [s.to_dict() for s in self.steps],
        }


class PlanManager:
    """Manager for creating and orchestrating strict execution plans."""

    def __init__(self, client: GoogleAI | None = None) -> None:
        self._client = client

    def create(
        self,
        goal: str,
        steps: list[str | PlanStep] | None = None,
        strict_order: bool = True,
        abort_on_failure: bool = True,
    ) -> StrictPlan:
        """Create a new strict plan."""
        return StrictPlan(
            goal=goal,
            steps=steps,
            strict_order=strict_order,
            abort_on_failure=abort_on_failure,
        )

    def execute(self, plan: StrictPlan) -> PlanExecutionResult:
        """Execute a plan using the attached client."""
        if self._client is None:
            raise RuntimeError("No GoogleAI client attached to PlanManager.")
        return plan.execute(self._client)
