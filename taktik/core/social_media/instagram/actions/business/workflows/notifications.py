"""Backward-compatible re-export. Actual implementation moved to notifications/workflow.py"""

from .notifications.workflow import NotificationsBusiness

__all__ = ["NotificationsBusiness"]
