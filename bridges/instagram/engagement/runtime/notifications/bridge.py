"""Instagram notifications engagement bridge runtime class.

Thin bridge: connect + bring Instagram to a known state, then delegate to the
core ``NotificationsEngagementWorkflow`` (which owns navigation + selectors). The
workflow stays stdout-free; this bridge injects a notifier mapping step callbacks
to JSON stdout events (Dependency Inversion).
"""

from __future__ import annotations

from bridges.instagram.engagement.runtime.notifications.events import emit_notif_step
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from taktik.core.social_media.instagram.workflows.management.notifications import (
    NotificationsEngagementWorkflow,
)


class NotificationsBridge(InstagramBridgeBase):
    """Bridge for the Instagram notifications engagement workflow."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)

    def build_workflow(self) -> NotificationsEngagementWorkflow:
        # relauncher lets a per-row action self-heal (restart IG + re-navigate) when
        # Instagram has drifted away from the notifications screen since the scan.
        return NotificationsEngagementWorkflow(
            self.device, self.device_id,
            notifier=emit_notif_step,
            relauncher=self.restart_instagram,
        )


__all__ = ["NotificationsBridge"]
