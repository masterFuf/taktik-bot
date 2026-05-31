"""Workflow registry for the Taktik Agent runtime kernel."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable

from taktik.core.agent.kernel.contracts import AgentPlan, WorkflowInvocation

WorkflowHandler = Callable[[WorkflowInvocation, Dict[str, Any]], Dict[str, Any]]


class WorkflowRegistry:
    """Register and resolve executable workflow handlers by canonical id."""

    def __init__(self) -> None:
        self._handlers: Dict[str, WorkflowHandler] = {}

    def register(self, workflow_id: str, handler: WorkflowHandler) -> None:
        if workflow_id in self._handlers:
            raise ValueError(f"Workflow '{workflow_id}' is already registered")
        self._handlers[workflow_id] = handler

    def resolve(self, workflow_id: str) -> WorkflowHandler:
        try:
            return self._handlers[workflow_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workflow '{workflow_id}'") from exc

    def missing_workflow_ids(self, workflow_ids: Iterable[str]) -> tuple[str, ...]:
        """Return unregistered workflow ids while preserving first-seen order."""
        missing: list[str] = []
        seen: set[str] = set()
        for workflow_id in workflow_ids:
            if workflow_id in seen:
                continue
            seen.add(workflow_id)
            if workflow_id not in self._handlers:
                missing.append(workflow_id)
        return tuple(missing)

    def missing_for_plan(self, plan: AgentPlan) -> tuple[str, ...]:
        """Return workflow ids that would fail registry resolution for this plan."""
        return self.missing_workflow_ids(
            step.workflow.workflow_id
            for step in plan.steps
            if step.kind == "workflow" and step.workflow is not None
        )

    def contains(self, workflow_id: str) -> bool:
        return workflow_id in self._handlers

    def workflow_ids(self) -> Iterable[str]:
        return tuple(sorted(self._handlers))
