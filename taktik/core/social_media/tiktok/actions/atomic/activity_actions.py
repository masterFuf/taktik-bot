"""Read the Activity page, and open what it points at.

This is the only surface that tells an account what its own content did: who liked it, saved it,
reposted it, commented on it, or just looked. For a bot it is the warmest audience there is --
these people acted first.

The reading is split in two on purpose. Getting the rows off the screen is here and depends on
the build; understanding what a row SAYS is `services/notifications/activity.py` and depends on
nothing, which is why it can be tested against 70 real rows without a phone.

As on every other TikTok list, a row names people by their DISPLAY NAME. Acting on one means
opening it.
"""

import time
from typing import Any, Dict, List, Optional

from ..core.base_action import BaseAction
from ..core.utils import first_matching
from ...ui.selectors.surfaces.activity import ACTIVITY_SELECTORS
from ...ui.selectors.surfaces.inbox import INBOX_SELECTORS
from ...services.notifications.activity import ActivityRow, parse_activity_row


class ActivityActions(BaseAction):
    """Open the Activity page and read what is on it."""

    def __init__(self, device):
        super().__init__(device)
        self.activity_selectors = ACTIVITY_SELECTORS
        self.inbox_selectors = INBOX_SELECTORS

    # ------------------------------------------------------------------

    def is_on_activity_page(self) -> bool:
        return bool(first_matching(self.device, self.activity_selectors.page_indicator))

    def open_activity(self, *, expand: bool = True) -> bool:
        """Open the Activity page from the inbox. True once the page is actually up.

        `expand` taps "Tout voir" when it is offered. Without it the page shows a handful of rows
        and stops, which reads exactly like an account nobody has interacted with.
        """
        if not self.is_on_activity_page():
            if not self._find_and_click(self.activity_selectors.activity_entry, timeout=5):
                self.logger.debug("open_activity: no Activity row in the inbox")
                return False
            time.sleep(3.0)

        if not self.is_on_activity_page():
            self.logger.warning("open_activity: the Activity page did not come up")
            return False

        if expand and self._find_and_click(self.activity_selectors.see_all_button, timeout=3):
            time.sleep(3.0)
        return True

    def read_activity(
        self,
        max_rows: int = 30,
        *,
        max_scrolls: int = 6,
    ) -> List[ActivityRow]:
        """The notifications on the page, parsed, newest first and de-duplicated.

        Scrolls until a pass brings nothing new rather than until the rows look the same: rows
        repeat verbatim -- twenty people liking a video on the same day produce twenty identical
        sentences apart from the name -- so comparing screenfuls compares nothing.
        """
        if not self.is_on_activity_page():
            self.logger.warning("read_activity: this is not the Activity page")
            return []

        collected: List[ActivityRow] = []
        seen = set()
        for _ in range(max_scrolls):
            found_here = 0
            for text in self._row_texts():
                if len(collected) >= max_rows:
                    break
                if text in seen:
                    continue
                seen.add(text)
                collected.append(parse_activity_row(text))
                found_here += 1

            if len(collected) >= max_rows or not found_here:
                break
            self._scroll_down(scale=0.7)
            time.sleep(1.2)

        unknown = sum(1 for row in collected if row.kind == "unknown")
        self.logger.info(
            f"🔔 {len(collected)} notification(s) lues"
            + (f", dont {unknown} de type inconnu" if unknown else "")
        )
        # Said out loud rather than swallowed: an unrecognised row means TikTok added a type, and
        # nobody finds that out from a count that only reports what it understood.
        for row in collected:
            if row.kind == "unknown":
                self.logger.warning(f"🔔 Type de notification inconnu: {row.raw[:90]!r}")
        return collected

    def open_row(self, index: int) -> bool:
        """Tap the notification at `index`. Where it lands depends on the kind: a like opens the
        video, a follow opens the profile. The caller is the one that knows which."""
        rows = first_matching(self.device, self.activity_selectors.row)
        if index >= len(rows):
            return False
        try:
            rows[index].click()
        except Exception as exc:
            self.logger.debug(f"open_row: row {index} not tappable ({exc})")
            return False
        self._human_like_delay('navigation')
        return True

    # ------------------------------------------------------------------

    def _row_texts(self) -> List[str]:
        texts: List[str] = []
        for element in first_matching(self.device, self.activity_selectors.row):
            text = (getattr(element, "text", "") or "").strip()
            if text:
                texts.append(text)
        return texts


__all__ = ["ActivityActions"]
