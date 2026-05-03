"""Threads automation module.

Provides the automation framework for Meta Threads (com.instagram.barcelona),
with a structure modelled on the Instagram module for consistency.

Main components:
- ThreadsManager: App lifecycle (launch, stop, detect install)
- UI: Package constants and selectors (populated from real UI dumps)

Status: MVP scaffolding. Workflows and actions are added incrementally.
"""

from .core.manager import ThreadsManager
from .ui import THREADS_PACKAGE, THREADS_MAIN_ACTIVITY

__all__ = [
    "ThreadsManager",
    "THREADS_PACKAGE",
    "THREADS_MAIN_ACTIVITY",
]
