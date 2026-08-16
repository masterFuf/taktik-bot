"""How the Gmail workflows talk back to whoever launched them.

A context-var notifier, so a workflow can emit progress without knowing whether it runs
under a bridge, the CLI, or nothing at all — in standalone the null notifier swallows it.

It lives apart from `account.py` because it is neither account management nor OTP reading:
both import it, and neither owns it.
"""

from contextvars import ContextVar
from functools import wraps
from typing import Optional, Protocol


class GmailWorkflowNotifier(Protocol):
    def status(self, status: str, message: str = "") -> None:
        ...

    def log(self, level: str, message: str) -> None:
        ...


class _NullNotifier:
    def status(self, status: str, message: str = "") -> None:
        return None

    def log(self, level: str, message: str) -> None:
        return None


_NULL_NOTIFIER = _NullNotifier()
_CURRENT_NOTIFIER: ContextVar[GmailWorkflowNotifier] = ContextVar(
    "gmail_workflow_notifier",
    default=_NULL_NOTIFIER,
)


class _NotifierProxy:
    def status(self, status: str, message: str = "") -> None:
        _CURRENT_NOTIFIER.get().status(status, message)

    def log(self, level: str, message: str) -> None:
        _CURRENT_NOTIFIER.get().log(level, message)


def _with_bound_notifier(method):
    @wraps(method)
    def wrapper(self, *args, **kwargs):
        token = _CURRENT_NOTIFIER.set(self._notifier)
        try:
            return method(self, *args, **kwargs)
        finally:
            _CURRENT_NOTIFIER.reset(token)

    return wrapper


_ipc = _NotifierProxy()


__all__ = [
    "GmailWorkflowNotifier",
    "_NullNotifier",
    "_NULL_NOTIFIER",
    "_CURRENT_NOTIFIER",
    "_with_bound_notifier",
    "_ipc",
]
