"""Mixin handling the interruptions of the TikTok video feed.

Handles the suggestion pages and the comment sections opened by accident
during the scroll.

Usable by any workflow inheriting the base video workflow.
"""

import time


class FeedInterruptionsMixin:
    """Mixin handling the common interruptions of the video feed.
    
    Requires:
        self.detection  — PopupDetector (has_suggestion_page, has_comments_section_open)
        self.click      — ClickActions (click_follow_back, click_not_interested, etc.)
        self.scroll     — ScrollActions (scroll_to_next_video)
        self.stats      — VideoWorkflowStats (suggestions_handled, users_followed)
        self.logger     — loguru logger
        self._send_stats_update() — callback to push stats
    """

    # Subclass may override (ForYouConfig sets it, SearchConfig defaults False)
    _follow_back_suggestions: bool = False

    def _handle_suggestion_page(self) -> bool:
        """Check for and handle suggestion page (Follow back / Not interested).
        
        Returns:
            True if a suggestion page was handled, False otherwise.
        """
        if not self.detection.has_suggestion_page():
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

    def _handle_comments_section(self) -> bool:
        """Check for and close comments section if accidentally opened.
        
        This can happen when scrolling and accidentally clicking on the
        comment input area.
        
        Returns:
            True if comments section was detected and closed, False otherwise.
        """
        if not self.detection.has_comments_section_open():
            return False

        self.logger.info("💬 Comments section detected, closing...")

        if self.click.close_comments_section():
            self.logger.info("✅ Comments section closed")
            time.sleep(0.5)
            return True

        self.logger.warning("⚠️ Failed to close comments section")
        return False
