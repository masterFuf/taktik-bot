"""The Instagram DM inbox capability set, composed once, and the runtime a host connects.

Read the inbox and its requests folder, open a conversation, reply in it. `DMRuntime` binds to a
device: it takes `device`, `screen_width` / `screen_height` and `_keyboard` (the Taktik Keyboard
service); a read or a reply also uses `restart_instagram()` and `device_manager` (the fallback
identity read visits our own profile). `dm_events` receives the events of a read, one per
conversation; without it they are dropped. `InstagramDMRuntime` is that set on the Instagram device
base, the one class the desktop DM bridge and the CLI connect (each says where the events of a read
go: the bridge's stdout, the CLI's log); the Cartography Lab binds `DMRuntime` to its warm device.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from taktik.core.shared.input.keyboard import KeyboardService
from taktik.core.social_media.instagram.workflows.common.device import InstagramDeviceBase
from taktik.core.social_media.instagram.workflows.dm.navigation import DMInboxNavigationMixin
from taktik.core.social_media.instagram.workflows.dm.reader import DMConversationReaderMixin
from taktik.core.social_media.instagram.workflows.dm.sender import DMSenderMixin


class DMRuntime(DMSenderMixin, DMConversationReaderMixin, DMInboxNavigationMixin):
    """The DM capability set.

    Kept as one composition so its mixin list has a single owner: the runtime a host connects
    extends it, and the diagnostics runtime binds it to an already-warm device instead of
    re-declaring the same mixins. Two compositions keep behaving identically right up until a mixin
    is added to one of them.
    """

    dm_events: Optional[Callable[[dict[str, Any]], None]] = None

    def _emit_dm_event(self, payload: dict[str, Any], *, flush: bool = False) -> None:
        if self.dm_events is not None:
            self.dm_events(payload)


class InstagramDMRuntime(DMRuntime, InstagramDeviceBase):
    """The DM capability set on the Instagram device (clone-aware proxy, facade, selector overrides,
    clean restart), with the Taktik Keyboard of its phone: what a host connects for a DM command."""

    def __init__(self, device_id: str, package_name: Optional[str] = None):
        super().__init__(device_id, package_name=package_name)
        self._keyboard = KeyboardService(device_id)


__all__ = ["DMRuntime", "InstagramDMRuntime"]
