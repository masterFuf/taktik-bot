"""Instagram notifications engagement workflow (management tier).

Production engagement workflow over the modern "Notifications" surface: scan and
classify the activity feed, and act on it (confirm/ignore follow requests, reply
to comment mentions). Selectors come from the centralized
``NOTIFICATION_SELECTORS`` catalog; this package adds no selector literal.
"""

from .classifier import classify_row, extract_time, row_has_action
from .notifications_workflow import NotificationsEngagementWorkflow

__all__ = [
    "NotificationsEngagementWorkflow",
    "classify_row",
    "extract_time",
    "row_has_action",
]
