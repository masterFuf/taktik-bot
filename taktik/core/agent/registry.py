"""Workflow registry for the Taktik Agent runtime kernel."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable

from taktik.core.agent.contracts import WorkflowInvocation

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

    def contains(self, workflow_id: str) -> bool:
        return workflow_id in self._handlers

    def workflow_ids(self) -> Iterable[str]:
        return tuple(sorted(self._handlers))
