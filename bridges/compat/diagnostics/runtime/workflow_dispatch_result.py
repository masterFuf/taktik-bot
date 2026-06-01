"""Shared dispatch result contract for compat workflow diagnostics."""

from dataclasses import dataclass


@dataclass
class WorkflowDispatchResult:
    success: bool = False
    error: str | None = None
    watchdog: object | None = None


__all__ = ["WorkflowDispatchResult"]
