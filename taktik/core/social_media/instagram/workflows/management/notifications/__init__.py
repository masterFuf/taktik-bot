"""Instagram notifications engagement workflow (management tier).

Production engagement workflow over the modern "Notifications" surface: scan and
classify the activity feed, and act on it (confirm/ignore follow requests, reply
to comment mentions). Selectors come from the centralized
``NOTIFICATION_SELECTORS`` catalog; this package adds no selector literal.
"""

from .classifier import classify_row, extract_time, row_has_action
from .notifications_workflow import NotificationsEngagementWorkflow
from .profile_pipeline import (
    DEFAULT_SUGGESTION_INTERACTION_CONFIG,
    NotificationsProfilePipeline,
    build_notifications_profile_pipeline,
)

__all__ = [
    "DEFAULT_SUGGESTION_INTERACTION_CONFIG",
    "NotificationsEngagementWorkflow",
    "NotificationsProfilePipeline",
    "build_notifications_profile_pipeline",
    "classify_row",
    "extract_time",
    "row_has_action",
]
