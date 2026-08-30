"""Collect the shareable link of the video on screen, and what identifies it.

The link comes from the share sheet: Share -> "Copy link" -> read the clipboard. Same road
Instagram takes, and it works on TikTok — measured 2026-08-30, the clipboard came back with
`https://vm.tiktok.com/ZN8FUVpSM/`.

What that link is NOT is an identity. Copying the same video's link four times in a row gave four
different shortcodes, and no numeric video id is rendered anywhere in the accessibility tree. So
this reads the three things the screen DOES show stably — author, post date, caption — and hands
them to `tiktok_post_key`. The link is stored for navigating; the key is stored for recognising.

SURFACE DIFFERENCE, measured 2026-08-30 through the Lab: a video opened FROM A PROFILE renders
`tv_post_time` (`· 06-12`), the FYP does not. On the FYP the identity therefore rests on author +
caption, and a caption-less video there cannot be identified at all — `collect_post` returns None
rather than key every silent video of an author to one row.

The clipboard can only be READ, not written: Android refuses `setPrimaryClip` from the automation
agent ("Package android does not belong to 2000"). A sentinel is therefore impossible, and telling
a fresh copy from a stale one is done by reading BEFORE and AFTER — which is what this does rather
than trusting the tap.
"""

import time
from typing import Any, Dict, Optional

from ..core.base_action import BaseAction
from ..core.utils import first_matching, first_text
from ...ui.selectors.surfaces.video import (
    VIDEO_ENGAGEMENT_SELECTORS,
    VIDEO_MEDIA_SELECTORS,
    VIDEO_SHARE_SELECTORS,
)
from ...ui.selectors.surfaces.video.creator import VIDEO_CREATOR_SELECTORS

#: What a copied TikTok link looks like, whichever shape the app hands out.
_LINK_MARKERS = ("tiktok.com", "vm.tiktok", "vt.tiktok")


class PostLinkActions(BaseAction):
    """Read the link and the identity of the video currently on screen."""

    def __init__(self, device):
        super().__init__(device)
        self.share_selectors = VIDEO_SHARE_SELECTORS
        self.engagement_selectors = VIDEO_ENGAGEMENT_SELECTORS
        self.media_selectors = VIDEO_MEDIA_SELECTORS
        self.creator_selectors = VIDEO_CREATOR_SELECTORS

    # ------------------------------------------------------------------

    def read_clipboard(self) -> str:
        """Whatever the clipboard holds, or an empty string when it cannot be read."""
        target = getattr(self.device, "_device", None) or self.device
        try:
            return (target.clipboard or "").strip()
        except Exception as exc:
            self.logger.debug(f"Clipboard unreadable: {exc}")
            return ""

    def copy_post_link(self, *, settle_seconds: float = 2.0) -> Optional[str]:
        """Open the share sheet, tap Copy link, and return what landed in the clipboard.

        Returns None when the sheet did not open, the entry was not found, or the clipboard did
        not change into something that looks like a TikTok link. Reporting the tap instead would
        hand the caller whatever the clipboard happened to hold from an earlier copy — which is
        exactly how a collector fills a table with one video's link repeated.
        """
        before = self.read_clipboard()

        if not self._find_and_click(self.engagement_selectors.share_button, timeout=4):
            self.logger.debug("copy_post_link: no share button on this screen")
            return None
        time.sleep(settle_seconds)

        if not self._find_and_click(self.share_selectors.copy_link_button, timeout=4):
            self.logger.warning("copy_post_link: 'Copy link' not offered by the share sheet")
            self._dismiss_sheet()
            return None
        time.sleep(settle_seconds)

        link = self.read_clipboard()
        self._dismiss_sheet()

        if not link or not any(marker in link for marker in _LINK_MARKERS):
            self.logger.warning(f"copy_post_link: the clipboard holds no TikTok link ({link[:40]!r})")
            return None
        if link == before:
            # Not proof of failure — copying the same video twice legitimately yields the same
            # string on platforms that mint a stable link. On TikTok it never does, so saying so
            # is worth a line rather than a silence.
            self.logger.debug("copy_post_link: the clipboard did not change")
        self.logger.info(f"🔗 {link}")
        return link

    def read_post_identity(self) -> Dict[str, Any]:
        """The three fields that identify the video on screen, read as the screen writes them.

        `author` is a DISPLAY NAME on this surface, not a handle — the handle is rendered nowhere
        on a video screen. That is fine for an identity, which only has to be stable, and it is
        why the key folds it rather than treating it as a username.
        """
        from .video_detector import VideoDetector

        return {
            # Through the detector that already answers this, not a second reading of the same
            # two nodes: `get_video_author` knows the label, the avatar description and every
            # prefix each language puts in front of it. A copy here was flagged by the
            # hardcoded-language audit within the hour, which is exactly what it is for.
            "author": VideoDetector(self.device).get_video_author() or "",
            "posted_at_label": first_text(self.device, self.media_selectors.post_time),
            "caption": first_text(self.device, self.media_selectors.video_description),
        }

    def collect_post(self) -> Optional[Dict[str, Any]]:
        """Link + identity + key for the video on screen, or None when the link could not be had.

        The identity is read BEFORE the sheet opens: the share sheet covers the caption and the
        date, so reading afterwards would return an empty caption and key every post of an author
        to the same row.
        """
        identity = self.read_post_identity()
        link = self.copy_post_link()
        if not link:
            return None

        from taktik.core.database.tiktok_post_identity import tiktok_post_key

        key = tiktok_post_key(
            identity.get("author"),
            identity.get("posted_at_label"),
            identity.get("caption"),
        )
        if not key:
            # Two ways to land here, and the log has to say which: no author at all, or -- the
            # common one on the FYP, where no post date is rendered -- a video with no caption
            # either. Both leave too little to tell this post from the author's next one.
            self.logger.warning(
                f"collect_post: not enough to identify this post "
                f"(author={identity.get('author')!r}, date={identity.get('posted_at_label')!r}, "
                f"caption={(identity.get('caption') or '')[:30]!r})"
            )
            return None
        return {**identity, "post_url": link, "post_key": key}

    # ------------------------------------------------------------------

    def _dismiss_sheet(self) -> None:
        """Leave no sheet behind: one left open hides the next video and swallows the swipe."""
        try:
            if first_matching(self.device, self.share_selectors.sheet_indicator):
                self.device.press("back")
                time.sleep(0.8)
        except Exception as exc:
            self.logger.debug(f"Could not dismiss the share sheet: {exc}")


__all__ = ["PostLinkActions"]
