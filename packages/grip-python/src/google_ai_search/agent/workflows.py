"""Workflow pipeline engine for automated multi-step execution."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from ..types.agent import WorkflowResult, WorkflowStep

if TYPE_CHECKING:
    from ..client import GoogleAI


class Workflow:
    """An automated execution pipeline chaining searches, tools, and formatters."""

    def __init__(self, name: str, description: str = "") -> None:
        self.name = name
        self.description = description
        self.steps: list[WorkflowStep] = []
        self._custom_handlers: dict[str, Callable[..., Any]] = {}

    def add_step(
        self,
        action: str,
        name: str | None = None,
        handler: Callable[..., Any] | None = None,
        **params: Any,
    ) -> Workflow:
        """Add an action step to the pipeline.

        Actions:
            - 'search': performs Google AI search query (params: query)
            - 'tool': invokes registered tool (params: tool_name, args/kwargs)
            - 'format': transforms previous response (params: style)
            - 'custom': runs custom callable handler
        """
        step_name = name or f"{action}_{len(self.steps) + 1}"
        step = WorkflowStep(name=step_name, action=action.lower().strip(), params=params)
        self.steps.append(step)
        if handler:
            self._custom_handlers[step_name] = handler
        return self

    def run(self, client: GoogleAI, initial_input: Any = None) -> WorkflowResult:
        """Execute the workflow steps sequentially."""
        start_time = time.time()
        ctx: dict[str, Any] = {"input": initial_input}
        last_output: Any = initial_input
        steps_completed = 0
        success = True

        for step in self.steps:
            try:
                if step.action == "search":
                    # Query can come from params or previous output
                    query = step.params.get("query")
                    if not query and isinstance(last_output, str):
                        query = last_output
                    elif not query:
                        query = str(initial_input or "Overview")
                    resp = client.search.query(query)
                    last_output = resp
                    ctx[step.name] = resp

                elif step.action == "tool":
                    tool_name = step.params.get("tool_name")
                    if not tool_name:
                        raise ValueError(f"Step '{step.name}' missing 'tool_name' parameter.")
                    # Pass previous output as primary arg if appropriate
                    tool_kwargs = dict(step.params.get("kwargs", {}))
                    if "text" not in tool_kwargs and isinstance(last_output, str):
                        tool_kwargs["text"] = last_output
                    elif "expression" not in tool_kwargs and tool_name == "calculator" and isinstance(last_output, str):
                        tool_kwargs["expression"] = last_output

                    result = client.tools.call(tool_name, **tool_kwargs)
                    last_output = result
                    ctx[step.name] = result

                elif step.action == "format":
                    style = step.params.get("style", "markdown")
                    if hasattr(last_output, "format"):
                        formatted = last_output.format(style=style)
                    elif hasattr(client, "formatters"):
                        formatted = client.formatters.format(last_output, style=style)
                    else:
                        formatted = str(last_output)
                    last_output = formatted
                    ctx[step.name] = formatted

                elif step.action == "custom":
                    handler = self._custom_handlers.get(step.name) or step.params.get("handler")
                    if not handler or not callable(handler):
                        raise ValueError(f"Step '{step.name}' has no callable custom handler.")
                    res = handler(ctx, client)
                    last_output = res
                    ctx[step.name] = res

                steps_completed += 1

            except Exception as exc:
                success = False
                ctx[f"{step.name}_error"] = str(exc)
                break

        duration = time.time() - start_time
        return WorkflowResult(
            workflow_name=self.name,
            success=success,
            steps_completed=steps_completed,
            output=last_output,
            step_outputs=ctx,
            duration_sec=duration,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "steps": [s.to_dict() for s in self.steps],
        }


class WorkflowManager:
    """Manager for registering, configuring, and executing workflows."""

    def __init__(self, client: GoogleAI | None = None) -> None:
        self._client = client
        self._workflows: dict[str, Workflow] = {}

    def create(self, name: str, description: str = "") -> Workflow:
        """Create a new workflow pipeline."""
        wf = Workflow(name=name, description=description)
        self._workflows[name] = wf
        return wf

    def get(self, name: str) -> Workflow | None:
        """Retrieve workflow by name."""
        return self._workflows.get(name)

    def list(self) -> list[Workflow]:
        """List registered workflows."""
        return list(self._workflows.values())

    def delete(self, name: str) -> bool:
        """Delete workflow by name."""
        return self._workflows.pop(name, None) is not None

    def run(self, name: str, initial_input: Any = None) -> WorkflowResult:
        """Run workflow by name using the attached client."""
        wf = self.get(name)
        if not wf:
            raise KeyError(f"Workflow '{name}' not found.")
        if not self._client:
            raise RuntimeError("No GoogleAI client attached to WorkflowManager.")
        return wf.run(self._client, initial_input=initial_input)
