"""Instagram DM bridge runtime class."""

from __future__ import annotations

from bridges.common.input.keyboard import KeyboardService
from bridges.instagram.engagement.runtime.dm.events import emit_dm_json
from bridges.instagram.runtime.bridge import InstagramBridgeBase
from taktik.core.social_media.instagram.workflows.dm_inbox.runtime import DMRuntime


class DMBridge(DMRuntime, InstagramBridgeBase):
    """The core DM runtime on the bridges' Instagram device (clone-aware proxy, facade, selector
    overrides, clean restart), with the Taktik Keyboard; a read's events go to stdout."""

    def __init__(self, device_id: str, package_name: str = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)
        self.dm_events = lambda payload: emit_dm_json(payload, flush=True)


__all__ = ["DMBridge", "DMRuntime"]
