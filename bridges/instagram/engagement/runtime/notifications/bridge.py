"""Instagram notifications engagement bridge runtime class.

Thin bridge: connect + bring Instagram to a known state, then delegate to the
core ``NotificationsEngagementWorkflow`` (which owns navigation + selectors). The
workflow stays stdout-free; this bridge injects a notifier mapping step callbacks
to JSON stdout events (Dependency Inversion).

It also injects the PER-PROFILE production pipeline the suggestions visit needs: the
core workflow owns no business action, no DB access and no session, so the object that
extracts / qualifies / follows / persists is built HERE and handed over — the very one
target and hashtag run.
"""

from __future__ import annotations

from typing import Any

from bridges.instagram.engagement.runtime.notifications.events import emit_notif_step
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from taktik.core.social_media.instagram.workflows.management.notifications import (
    NotificationsEngagementWorkflow,
    build_notifications_profile_pipeline,
)


class NotificationsBridge(InstagramBridgeBase):
    """Bridge for the Instagram notifications engagement workflow."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)

    def build_workflow(self, profile_pipeline: Any = None) -> NotificationsEngagementWorkflow:
        # relauncher lets a per-row action self-heal (restart IG + re-navigate) when
        # Instagram has drifted away from the notifications screen since the scan.
        return NotificationsEngagementWorkflow(
            self.device, self.device_id,
            notifier=emit_notif_step,
            relauncher=self.restart_instagram,
            profile_pipeline=profile_pipeline,
        )

    def build_profile_pipeline(self, *, account_id: int, config: dict | None = None):
        """Per-profile production pipeline bound to THIS phone's account.

        ``account_id`` is required and never defaulted: every follow this pipeline lands
        is written under it, and the historical fallback (id 1) would file another
        account's actions — silently, into the very table the daily caps read.
        """
        return build_notifications_profile_pipeline(
            self.device, config=config, account_id=account_id,
        )


__all__ = ["NotificationsBridge"]
