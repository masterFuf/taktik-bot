"""Instagram DM bridge runtime class."""

from __future__ import annotations

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.engagement.runtime.dm.navigation import DMInboxNavigationMixin
from bridges.instagram.engagement.runtime.dm.reader import DMConversationReaderMixin
from bridges.instagram.engagement.runtime.dm.sender import DMSenderMixin
from bridges.instagram.runtime.bridge import InstagramBridgeBase


class DMBridge(DMSenderMixin, DMConversationReaderMixin, DMInboxNavigationMixin, InstagramBridgeBase):
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)


__all__ = ["DMBridge"]
