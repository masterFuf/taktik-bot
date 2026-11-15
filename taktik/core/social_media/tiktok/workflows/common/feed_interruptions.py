"""Mixin handling the interruptions of the TikTok video feed.

Handles the suggestion pages and the comment sections opened by accident
during the scroll, and a creator's profile the feed ended up on.

Usable by any workflow inheriting the base video workflow.
"""

import time
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from taktik.core.social_media.tiktok.actions.atomic.detection.detection_actions import DetectionActions
    from taktik.core.social_media.tiktok.actions.atomic.interaction.click_actions import ClickActions
    from taktik.core.social_media.tiktok.actions.atomic.scroll.scroll_actions import ScrollActions
    from taktik.core.social_media.tiktok.workflows.common.models import VideoWorkflowStats

#: Failed returns to the feed in a row after which the run stops (`navigation_failed`).
MAX_FAILED_RETURNS_TO_FEED = 3


class FeedInterruptionsMixin:
    """Mixin handling the common interruptions of the video feed.

    Requires:
        self.detection  — PopupDetector (has_suggestion_page, has_comments_section_open)
        self.click      — ClickActions (click_follow_back, click_not_interested, etc.)
        self.scroll     — ScrollActions (scroll_to_next_video)
        self.stats      — VideoWorkflowStats (suggestions_handled, users_followed)
        self.logger     — loguru logger
        self._send_stats_update() — callback to push stats
        self._return_to_video_feed() — the workflow's way back to its feed, True once there
        self.stop()     — ends the run's loop
    """

    # What the host (`BaseVideoWorkflow`) provides, declared as an interface would be (no value:
    # nothing is shadowed).
    detection: "DetectionActions"
    click: "ClickActions"
    scroll: "ScrollActions"
    stats: "VideoWorkflowStats"
    logger: Any
    _send_stats_update: Callable[[], None]
    _stop_if_action_blocked: Callable[[str, str], bool]
    stop: Callable[[], None]

    # Subclass may override (ForYouConfig sets it, SearchConfig defaults False)
    _follow_back_suggestions: bool = False

    # Returns to the feed that failed in a row; set on the instance by the first failure.
    _failed_returns_to_feed: int = 0

    def _return_to_video_feed(self) -> bool:
        """Bring the screen back to the workflow's feed of videos. Each feed workflow says how."""
        raise NotImplementedError(f"{type(self).__name__} does not say how it returns to its feed")

    def _leave_profile_surface(self, screen) -> bool:
        """Leave a creator's profile the feed ended up on. True when this turn's photo was one.

        A profile is not a video: before this, the turn sent the desktop a video card without an
        author, "watched" the profile, counted a video, then swiped its grid, and the next turns
        did the same. Here nothing is counted and the workflow returns to its feed; a return
        that fails counts an error, and `MAX_FAILED_RETURNS_TO_FEED` of them in a row stop the run
        with the motive `navigation_failed`.

        Args:
            screen: the photo this turn was read on (`detection.read_screen()`).
        """
        if screen is None or screen.kind != "profile":
            return False

        self.logger.warning("👤 A creator's profile is on screen, not a video: back to the feed")
        if self._return_to_video_feed():
            self._failed_returns_to_feed = 0
            return True

        self._failed_returns_to_feed += 1
        self.stats.errors += 1
        self._send_stats_update()
        self.logger.error(
            f"❌ Return to the feed failed ({self._failed_returns_to_feed}/{MAX_FAILED_RETURNS_TO_FEED})"
        )
        if self._failed_returns_to_feed >= MAX_FAILED_RETURNS_TO_FEED:
            self.logger.error("🚨 The feed cannot be reached any more: stopping")
            self.stats.completion_reason = "navigation_failed"
            self.stop()
        return True

    def _handle_suggestion_page(self, screen=None) -> bool:
        """Check for and handle suggestion page (Follow back / Not interested).

        Args:
            screen: the photo this turn was read on; after a gesture, new photos.

        Returns:
            True if a suggestion page was handled, False otherwise.
        """
        if not self.detection.has_suggestion_page(screen):
            return False

        self.logger.info("💡 Suggestion page detected")

        # Resolve the flag from self.config if available, else use class default
        follow_back = getattr(
            getattr(self, 'config', None), 'follow_back_suggestions',
            self._follow_back_suggestions,
        )

        handled = False

        if follow_back:
            self.logger.info("👤 Following back suggested user")
            if self.click.click_follow_back():
                if self._stop_if_action_blocked('', 'follow back'):
                    return True
                self.stats.suggestions_handled += 1
                self.stats.users_followed += 1
                self._send_stats_update()
                time.sleep(1)
                handled = True
        else:
            self.logger.info("❌ Clicking 'Not interested'")
            if self.click.click_not_interested():
                self.stats.suggestions_handled += 1
                self._send_stats_update()
                time.sleep(1)
                handled = True

        # Fallback: try to close via X button
        if not handled:
            if self.click.close_suggestion_page():
                self.stats.suggestions_handled += 1
                self._send_stats_update()
                time.sleep(0.5)
                handled = True

        # Ultimate fallback: swipe up to skip
        if not handled:
            self.logger.info("⬆️ Swiping up to skip suggestion page")
            self.scroll.scroll_to_next_video()
            self.stats.suggestions_handled += 1
            self._send_stats_update()
            time.sleep(1)
            return True

        # After handling, swipe up if suggestion page persists
        if handled:
            time.sleep(0.5)
            if self.detection.has_suggestion_page():
                self.logger.info("⬆️ Still on suggestion page, swiping up")
                self.scroll.scroll_to_next_video()
                time.sleep(1)

        return True

    def _handle_comments_section(self, screen=None) -> bool:
        """Check for and close comments section if accidentally opened.
        
        This can happen when scrolling and accidentally clicking on the
        comment input area.

        Args:
            screen: the photo this turn was read on.

        Returns:
            True if comments section was detected and closed, False otherwise.
        """
        if not self.detection.has_comments_section_open(screen):
            return False

        self.logger.info("💬 Comments section detected, closing...")

        if self.click.close_comments_section():
            self.logger.info("✅ Comments section closed")
            time.sleep(0.5)
            return True

        self.logger.warning("⚠️ Failed to close comments section")
        return False
