"""Instagram notifications engagement bridge runtime class.

Thin bridge: connect and bring Instagram to a known state. The run itself (the core
``NotificationsEngagementWorkflow``, its per-profile pipeline, persistence and the batch) is
``run_instagram_notifications``, which receives this object as its connected runtime.
"""

from __future__ import annotations

from bridges.instagram.runtime.bridge import InstagramBridgeBase


class NotificationsBridge(InstagramBridgeBase):
    """Bridge for the Instagram notifications engagement workflow."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)


__all__ = ["NotificationsBridge"]
