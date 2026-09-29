"""Structured runtime errors for the Taktik Agent kernel."""

from __future__ import annotations


class MissingWorkflowHandlersError(ValueError):
    """Raised when a valid agent plan references workflows without handlers."""

    error_type = "missing_workflow_handlers"

    def __init__(self, workflow_ids: tuple[str, ...]) -> None:
        self.workflow_ids = workflow_ids
        joined = ", ".join(workflow_ids)
        super().__init__(f"No workflow handler registered for: {joined}")

    def to_payload(self) -> dict[str, object]:
        """Return a JSON-safe error payload for bridges or standalone callers."""
        return {
            "error_type": self.error_type,
            "message": str(self),
            "workflow_ids": list(self.workflow_ids),
        }
