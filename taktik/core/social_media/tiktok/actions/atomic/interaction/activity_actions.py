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

from ...core.base_action import BaseAction
from ...core.utils import first_matching
from ....ui.selectors.surfaces.activity import ACTIVITY_SELECTORS
from ....ui.selectors.surfaces.inbox import INBOX_SELECTORS
from ....services.notifications.activity import ActivityRow, parse_activity_row


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

    def read_suggested_accounts(self) -> List[Dict[str, Any]]:
        """The accounts TikTok is suggesting at the bottom of the Activity summary.

        On the SUMMARY, never on the expanded list: measured 2026-08-30, ten scrolls down the
        "Tout voir" list found no block at all, and the same page opened without expanding shows
        it straight away. `open_activity(expand=False)` is what gets here.

        The names are DISPLAY NAMES, as everywhere. They are usable for tapping the row -- which
        is what they are for -- and not for filing anyone under.
        """
        found: List[Dict[str, Any]] = []
        for element in first_matching(self.device, self.activity_selectors.suggested_account_rows):
            description = (getattr(element, "info", {}) or {}).get("contentDescription") or ""
            name = self._name_in_remove_label(description)
            if name and all(row["name"] != name for row in found):
                found.append({"name": name, "label": description})
        self.logger.info(f"🔔 {len(found)} compte(s) suggéré(s)")
        return found

    def follow_suggested_account(self, shown_name: str) -> bool:
        """Follow ONE suggested account. True once its row stops offering the button.

        The outcome, not the tap. TikTok replaces the button with a state the moment the follow
        lands, so its disappearance from that row is the readable proof -- and the row is scoped
        by name, so a disappearance elsewhere on the page proves nothing about this one.
        """
        name = (shown_name or "").strip()
        if not name:
            return False

        selectors = self.activity_selectors.suggested_follow_button_for_name(name)
        if not self._find_and_click(selectors, timeout=4):
            self.logger.warning(f"Bouton « Suivre » introuvable pour {name!r}")
            return False
        self._human_like_delay('navigation')

        deadline = time.time() + 6.0
        while time.time() < deadline:
            if not first_matching(self.device, selectors):
                self.logger.info(f"➕ Suggestion suivie : {name!r}")
                return True
            time.sleep(0.8)

        self.logger.warning(f"follow_suggested_account: {name!r} propose toujours « Suivre »")
        return False

    @staticmethod
    def _name_in_remove_label(description: str) -> str:
        """`Supprimer <NAME> des comptes suggérés` -> `<NAME>`.

        Both languages, and both ends trimmed rather than split on a separator: a display name
        can contain anything, spaces and the word "des" included.
        """
        for prefix, suffix in (
            ("Supprimer ", " des comptes suggérés"),
            ("Remove ", " from suggested accounts"),
        ):
            if description.startswith(prefix) and description.endswith(suffix):
                return description[len(prefix):-len(suffix)].strip()
        return ""

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
