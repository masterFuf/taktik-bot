"""The sound a video uses, and the people who used it too.

A sound is a targeting source TikTok has and Instagram does not. Every video carries one, that
sound has a page, and the page lists every video made with it -- so "everyone riding this trend"
is a reachable audience in a way "everyone who posted this word" never quite is.

Measured on 46.6.3 on 2026-08-30, and the numbers are the point: our own original audio had
3 posts, `Umbrella - Rihanna` had 3.3 million. Reading that count before harvesting is what keeps
a run from spending twenty minutes on a sound nobody uses.

The cost is the same three-step road every list on this app forces. A sound-page cell carries
`content-desc="Vidéo"` and names nobody, so a handle means: open the cell, read the author off the
video, open the author, read the handle. Measured end to end -- the cell behind `мішонк бро`
belongs to @mniuwuu, which no search for that name would ever have found.

MEASURED GAP, stated rather than hidden: reaching a sound BY NAME through the search Sounds tab
does not work here. The tab is found and tapped and the list stays empty past twelve seconds. So
a sound is reached from a video that uses it. Naming one in a config is not yet possible.
"""

import re
import time
from typing import Any, Dict, List, Optional

from ..core.base_action import BaseAction
from ..core.utils import first_matching, first_text, parse_count
from ...ui.selectors.surfaces.video import VIDEO_SOUND_SELECTORS
from ...ui.selectors.surfaces.video.creator import VIDEO_CREATOR_SELECTORS
from ...services.profile.username import read_open_profile_handle

#: `Umbrella Rihanna <bidi>3,3 M publications` -> the count, whatever separators the locale uses.
_COUNT_IN_TITLE = re.compile(r"([\d  .,]+\s*[KkMmBb]?[dD]?)\s*(?:publication|post)", re.IGNORECASE)


class SoundActions(BaseAction):
    """Read the sound of the video on screen, and harvest who else used it."""

    def __init__(self, device):
        super().__init__(device)
        self.sound_selectors = VIDEO_SOUND_SELECTORS
        self.creator_selectors = VIDEO_CREATOR_SELECTORS

    # ------------------------------------------------------------------

    def read_current_sound(self) -> str:
        """The sound label of the video on screen, exactly as the screen writes it.

        `Son : Umbrella par Rihanna` -- title and author in one string, and no id anywhere. It is
        a label, not an identifier, which is why nothing here tries to key on it.
        """
        for element in first_matching(self.device, self.sound_selectors.sound_entry):
            description = (getattr(element, "info", {}) or {}).get("contentDescription") or ""
            if description:
                return description.strip()
            text = (getattr(element, "text", "") or "").strip()
            if text:
                return text
        return ""

    def open_sound_page(self, *, settle_seconds: float = 6.0) -> bool:
        """Open the page of the sound this video uses. True only once that page is up.

        Arrival, not the tap: the sound row sits next to the caption and the author, and a tap
        that missed lands on one of those. A caller told "we are on the sound page" when it is on
        a profile harvests that profile's videos instead of the sound's.
        """
        if not self._find_and_click(self.sound_selectors.sound_entry, timeout=4):
            self.logger.debug("open_sound_page: no sound row on this screen")
            return False
        time.sleep(settle_seconds)

        if not first_matching(self.device, self.sound_selectors.sound_page_indicator):
            self.logger.warning("open_sound_page: the sound page did not come up")
            return False
        return True

    def sound_post_count(self) -> Optional[int]:
        """How many videos use this sound, or None when the page does not say.

        None is not zero. A sound page that could not be read and a sound nobody uses lead to
        opposite decisions, and a run that treats the first as the second skips real trends.
        """
        for text in self._page_labels():
            match = _COUNT_IN_TITLE.search(text)
            if match:
                return parse_count(match.group(1))
        return None

    def collect_sound_users(
        self,
        max_users: int = 20,
        *,
        max_scrolls: int = 6,
    ) -> List[Dict[str, Any]]:
        """The handles behind the videos on the open sound page.

        Costs about 20 seconds per person: cell -> video -> author -> profile -> back -> back.
        That is what a handle costs on this surface, and it is why `max_users` is a budget rather
        than a hope.
        """
        if not first_matching(self.device, self.sound_selectors.sound_page_indicator):
            self.logger.warning("collect_sound_users: this is not a sound page")
            return []

        collected: Dict[str, Dict[str, Any]] = {}
        for _ in range(max_scrolls):
            cells = first_matching(self.device, self.sound_selectors.sound_video_cell)
            if not cells:
                self.logger.debug("collect_sound_users: no video cell on this screenful")
                break

            found_here = 0
            for index in range(len(cells)):
                if len(collected) >= max_users:
                    break
                record = self._handle_behind_cell(index)
                if record and record["username"] not in collected:
                    collected[record["username"]] = record
                    found_here += 1
                    self.logger.info(
                        "\U0001f3b5 {0!r} -> @{1}".format(record["display_name"], record["username"])
                    )

            if len(collected) >= max_users:
                break
            # "This pass brought nobody new", never "the cells look the same": the cells carry no
            # text at all, so comparing them compares nothing.
            if not found_here:
                self.logger.debug("collect_sound_users: a full pass brought nobody new")
                break
            self._scroll_down(scale=0.6)
            time.sleep(1.5)

        self.logger.info(f"\U0001f3b5 {len(collected)} sound user(s) identified")
        return list(collected.values())

    # ------------------------------------------------------------------

    def _handle_behind_cell(self, index: int) -> Optional[Dict[str, Any]]:
        """Open the cell at `index`, resolve the author's handle, and come back to the grid."""
        cells = first_matching(self.device, self.sound_selectors.sound_video_cell)
        if index >= len(cells):
            return None

        try:
            cells[index].click()
        except Exception as exc:
            self.logger.debug(f"collect_sound_users: cell {index} not tappable ({exc})")
            return None
        time.sleep(4.0)

        display_name = first_text(self.device, self.creator_selectors.author_username)
        handle = ""
        if self._find_and_click(self.creator_selectors.author_username, timeout=4):
            time.sleep(3.0)
            handle = read_open_profile_handle(self.device, label=display_name, timeout=6)
            self.device.press("back")
            time.sleep(1.5)

        self.device.press("back")
        time.sleep(1.5)

        if not first_matching(self.device, self.sound_selectors.sound_video_cell):
            self.logger.warning("collect_sound_users: lost the sound grid on the way back")
            return None
        if not handle:
            return None
        return {"username": handle, "display_name": display_name}

    def _page_labels(self) -> List[str]:
        """Every label the sound page renders that could carry the count."""
        labels: List[str] = []
        for element in first_matching(self.device, self.sound_selectors.sound_page_indicator):
            info = getattr(element, "info", {}) or {}
            for value in (info.get("contentDescription"), getattr(element, "text", "")):
                if value:
                    labels.append(str(value))
        return labels


__all__ = ["SoundActions"]
