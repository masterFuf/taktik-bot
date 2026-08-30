"""Teach the For You page what this account is about.

The For You feed is the one surface where an account's future reach is decided by what it watched
rather than by what it posted, and TikTok is unusual in exposing a control for it: `Pas
interesse(e)` / `Not interested`, in the share sheet. Nothing on Instagram corresponds.

A training pass therefore has three gestures, in order of how loudly they speak:

    watched through   a positive signal, the strongest one that costs nothing
    skipped early     a weak negative, which is what a fast swipe already means
    not interested    an explicit negative, and the only one TikTok takes as a statement

Measured on 46.6.3 on 2026-08-30: tapping "Pas interesse(e)" closes the sheet AND advances to the
next video by itself -- the author went from `Anaïs` to `dylsmoove` with no swipe. That change of
author is the only readable proof the signal left, so it is what this checks. The tap itself
reports success whether or not the sheet was even open.
"""

import time
from typing import Optional

from ..core.base_action import BaseAction
from ..core.utils import first_matching, first_text
from ...ui.selectors.surfaces.video import (
    VIDEO_ENGAGEMENT_SELECTORS,
    VIDEO_SHARE_SELECTORS,
)
from ...ui.selectors.surfaces.video.creator import VIDEO_CREATOR_SELECTORS


class FeedTrainingActions(BaseAction):
    """The gestures that tell the For You algorithm what to send next."""

    def __init__(self, device):
        super().__init__(device)
        self.share_selectors = VIDEO_SHARE_SELECTORS
        self.engagement_selectors = VIDEO_ENGAGEMENT_SELECTORS
        self.creator_selectors = VIDEO_CREATOR_SELECTORS

    # ------------------------------------------------------------------

    def mark_not_interested(self, *, settle_seconds: float = 4.0) -> bool:
        """Send the explicit "less of this" signal. True once the feed has actually moved on.

        Returns False when the sheet would not open, when the entry is not offered, or when the
        video on screen afterwards is the same one. That last check is the whole point: the tap
        succeeds regardless, and a pass that counted taps would report a trained feed after
        sending nothing.
        """
        before = self._current_author()

        if not self._open_sheet():
            self.logger.debug("mark_not_interested: no share sheet on this screen")
            return False

        if not self._find_and_click(self.share_selectors.not_interested_button, timeout=4):
            self.logger.warning("mark_not_interested: the sheet offers no 'Not interested' entry")
            self._dismiss_sheet()
            return False
        time.sleep(settle_seconds)

        after = self._current_author()
        if after and before and after == before:
            # Same video still up. Either the tap missed or TikTok refused it; both mean the
            # signal did not leave, and both need the caller to move the feed itself.
            self.logger.warning(
                f"mark_not_interested: still on {before!r} — the signal did not go through"
            )
            self._dismiss_sheet()
            return False

        self.logger.info(f"👎 « Pas intéressé » sur {before!r} → {after!r}")
        return True

    def watch_through(self, seconds: float) -> None:
        """Stay on the video. The strongest positive signal there is, and it costs nothing.

        Deliberately dumb: no tap, no gesture, just time on screen. Anything else added here would
        be a second signal riding on the first, and the caller decides those separately.
        """
        time.sleep(max(0.0, seconds))

    # ------------------------------------------------------------------

    def _current_author(self) -> str:
        """Who the video on screen belongs to, as the screen writes it.

        A display name, not a handle -- which is fine, because this is used to tell one video from
        the next, never to identify a person.
        """
        return first_text(self.device, self.creator_selectors.author_username)

    def _open_sheet(self) -> bool:
        if first_matching(self.device, self.share_selectors.sheet_indicator):
            return True
        if not self._find_and_click(self.engagement_selectors.share_button, timeout=4):
            return False
        time.sleep(2.0)
        return bool(first_matching(self.device, self.share_selectors.sheet_indicator))

    def _dismiss_sheet(self) -> None:
        try:
            if first_matching(self.device, self.share_selectors.sheet_indicator):
                self.device.press("back")
                time.sleep(0.8)
        except Exception as exc:
            self.logger.debug(f"Could not dismiss the share sheet: {exc}")


__all__ = ["FeedTrainingActions"]
