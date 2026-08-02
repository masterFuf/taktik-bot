"""Instagram DM bridge runtime class."""

from __future__ import annotations

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.engagement.runtime.dm.navigation import DMInboxNavigationMixin
from bridges.instagram.engagement.runtime.dm.reader import DMConversationReaderMixin
from bridges.instagram.engagement.runtime.dm.sender import DMSenderMixin
from bridges.instagram.runtime.bridge import InstagramBridgeBase


class DMRuntime(DMSenderMixin, DMConversationReaderMixin, DMInboxNavigationMixin):
    """The DM capability set, composed once.

    Kept apart from the bridge so the mixin list has a single owner: the production
    bridge below extends it, and the Cartography Lab binds it to an already-warm
    device instead of re-declaring the same three mixins. Two compositions keep
    behaving identically right up until a mixin is added to one of them.

    Assembling it only requires ``device``, ``screen_width`` / ``screen_height`` and
    ``_keyboard`` — no other bridge coupling.
    """


class DMBridge(DMRuntime, InstagramBridgeBase):
    """Bridge for DM operations between TAKTIK Desktop and Instagram."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)


__all__ = ["DMBridge", "DMRuntime"]
