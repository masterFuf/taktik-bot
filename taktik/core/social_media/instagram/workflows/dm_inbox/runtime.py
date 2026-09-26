"""The Instagram DM inbox capability set, composed once.

Read the inbox and its requests folder, open a conversation, reply in it. It was the DM bridge's
runtime; the desktop bridge (`DMBridge`), the CLI and the Cartography Lab now bind this one class to
their device. Binding it takes `device`, `screen_width` / `screen_height` and `_keyboard` (the
Taktik Keyboard service); a read or a reply also uses `restart_instagram()` and `device_manager`
(the fallback identity read visits our own profile). `dm_events` receives the events of a read, one
per conversation (the desktop bridge prints them on stdout); without it they are dropped.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

from taktik.core.social_media.instagram.workflows.dm_inbox.navigation import DMInboxNavigationMixin
from taktik.core.social_media.instagram.workflows.dm_inbox.reader import DMConversationReaderMixin
from taktik.core.social_media.instagram.workflows.dm_inbox.sender import DMSenderMixin


class DMRuntime(DMSenderMixin, DMConversationReaderMixin, DMInboxNavigationMixin):
    """The DM capability set.

    Kept as one composition so its mixin list has a single owner: the production bridge extends
    it, and the diagnostics runtime binds it to an already-warm device instead of re-declaring the
    same mixins. Two compositions keep behaving identically right up until a mixin is added to one
    of them.
    """

    dm_events: Optional[Callable[[dict[str, Any]], None]] = None

    def _emit_dm_event(self, payload: dict[str, Any], *, flush: bool = False) -> None:
        if self.dm_events is not None:
            self.dm_events(payload)


__all__ = ["DMRuntime"]
