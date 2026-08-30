"""Repost the video on screen, and know whether it was already reposted.

TikTok has no Instagram equivalent for this: a repost puts someone else's video on your own
profile under your name. It is the cheapest way to feed a profile that has nothing to post yet,
and it is a real signal to the author -- which is why it belongs beside like and comment rather
than in a workflow of its own.

Two things the screen forced, both measured on 46.6.3 on 2026-08-30:

- The repost lands ON THE TAP. What comes up afterwards is not a confirmation, which is what the
  first version of this file assumed and got wrong: the first time it is an explainer ("Elle
  apparaitra sur ton profil" + OK), and every time after that it is a NOTE COMPOSER whose Ajouter
  button is `enabled="false"` while the note is empty. Written as a confirmation, this action
  worked once and then reported failure forever. Closing the composer without writing anything
  leaves the video reposted -- that is the measurement that settles what the screen is doing.
- A reposted video is readable. The sheet entry changes from `Republier` to `Supprimer la
  republication`, which is both the proof the repost landed and the guard against doing it twice.
"""

import time
from typing import Optional

from ...core.base_action import BaseAction
from ...core.utils import first_matching
from ....ui.selectors.surfaces.video import (
    VIDEO_ENGAGEMENT_SELECTORS,
    VIDEO_SHARE_SELECTORS,
)


class RepostActions(BaseAction):
    """Repost the video currently on screen."""

    def __init__(self, device):
        super().__init__(device)
        self.share_selectors = VIDEO_SHARE_SELECTORS
        self.engagement_selectors = VIDEO_ENGAGEMENT_SELECTORS

    # ------------------------------------------------------------------

    def is_reposted(self, *, sheet_already_open: bool = False) -> Optional[bool]:
        """True / False for the video on screen, or None when the sheet could not be opened.

        None is not False. "We could not look" and "it is not reposted" lead to opposite actions,
        and collapsing them is how a bot reposts the same video on every pass.
        """
        if not sheet_already_open and not self._open_sheet():
            return None

        reposted = bool(first_matching(self.device, self.share_selectors.repost_done_indicator))
        if not sheet_already_open:
            self._dismiss_sheet()
        return reposted

    def repost_video(self, *, settle_seconds: float = 2.5) -> bool:
        """Repost the video on screen. True only once the sheet says it IS reposted.

        Already reposted counts as success: the caller asked for the video to be on the profile,
        and it is. Saying otherwise would push a retry loop into doing nothing forever.
        """
        if not self._open_sheet():
            self.logger.debug("repost_video: no share sheet on this screen")
            return False

        if first_matching(self.device, self.share_selectors.repost_done_indicator):
            self.logger.info("🔁 Déjà republiée")
            self._dismiss_sheet()
            return True

        if not self._find_and_click(self.share_selectors.repost_button, timeout=4):
            self.logger.warning("repost_video: the share sheet offers no Repost entry")
            self._dismiss_sheet()
            return False
        time.sleep(settle_seconds)

        self._close_followup()

        # The outcome, read from the sheet itself. Nothing before this line is evidence: the tap
        # reports success whether or not the repost landed, and the follow-up screen is optional.
        confirmed = self.is_reposted()
        if confirmed:
            self.logger.success("🔁 Vidéo republiée")
            return True
        self.logger.warning(f"repost_video: tapped, but the sheet reads reposted={confirmed!r}")
        return False

    def _close_followup(self, *, timeout: float = 6.0) -> None:
        """Clear whatever the repost opened behind it, so the next step sees a video screen.

        Deliberately NOT a failure when there is nothing to close: the repost has already landed
        by this point, and some passes show no follow-up at all. Leaving one open, on the other
        hand, hides the next video and swallows the swipe.
        """
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._find_and_click(self.share_selectors.repost_followup_close, timeout=1.5):
                time.sleep(1.5)
                return
            time.sleep(0.5)
        self.logger.debug("repost_video: no follow-up screen to close")

    def undo_repost(self) -> bool:
        """Remove a repost. True once the sheet stops saying the video is reposted."""
        if not self._open_sheet():
            return False
        if not first_matching(self.device, self.share_selectors.repost_done_indicator):
            self.logger.debug("undo_repost: this video is not reposted")
            self._dismiss_sheet()
            return True

        if not self._find_and_click(self.share_selectors.repost_done_indicator, timeout=4):
            self._dismiss_sheet()
            return False
        time.sleep(2.5)

        # Removing can raise a follow-up of its own; clearing one that is not there costs nothing.
        self._close_followup(timeout=3.0)
        time.sleep(1.5)

        still = self.is_reposted()
        if still is False:
            self.logger.info("🔁 Republication retirée")
            return True
        self.logger.warning(f"undo_repost: the sheet still reads reposted={still!r}")
        return False

    # ------------------------------------------------------------------

    def _open_sheet(self) -> bool:
        """Open the share sheet, or say it could not be opened. Idempotent when already up."""
        if first_matching(self.device, self.share_selectors.sheet_indicator):
            return True
        if not self._find_and_click(self.engagement_selectors.share_button, timeout=4):
            return False
        time.sleep(2.0)
        return bool(first_matching(self.device, self.share_selectors.sheet_indicator))

    def _dismiss_sheet(self) -> None:
        """Leave no sheet behind: one left open hides the next video and swallows the swipe."""
        try:
            if first_matching(self.device, self.share_selectors.sheet_indicator):
                self.device.press("back")
                time.sleep(0.8)
        except Exception as exc:
            self.logger.debug(f"Could not dismiss the share sheet: {exc}")


__all__ = ["RepostActions"]
