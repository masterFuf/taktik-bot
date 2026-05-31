"""Notifier context helpers for standalone TikTok workflows.

Workflows stay usable without a bridge while allowing bridges to inject their
own notifier at execution time.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any

from loguru import logger


class NullWorkflowNotifier:
    """No-op notifier used by standalone workflows without live events."""

    def status(self, *args: Any, **kwargs: Any) -> None:
        return None

    def log(self, *args: Any, **kwargs: Any) -> None:
        return None


class LoggingWorkflowNotifier:
    """Fallback notifier that mirrors workflow events to the Python logger."""

    def log(self, level: str, message: str) -> None:
        logger.info(message)

    def status(self, status: str, message: str = "") -> None:
        logger.info(f"[{status}] {message}")


class WorkflowNotifierProxy:
    """Resolve notifier calls from the current workflow execution context."""

    def __init__(self, current_notifier: ContextVar[Any]):
        self._current_notifier = current_notifier

    def __getattr__(self, name: str) -> Any:
        return getattr(self._current_notifier.get(), name)


def create_workflow_notifier_context(
    name: str,
    *,
    default: Any | None = None,
) -> tuple[Any, ContextVar[Any], WorkflowNotifierProxy]:
    """Create the fallback, context var and proxy used by one workflow module."""
    fallback = default or NullWorkflowNotifier()
    current_notifier: ContextVar[Any] = ContextVar(name, default=fallback)
    return fallback, current_notifier, WorkflowNotifierProxy(current_notifier)
