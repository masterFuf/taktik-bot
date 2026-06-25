"""Story interaction actions (profile rings, feed stories, highlights, reactions)."""

from typing import Optional

from ...core.base_action import BaseAction
from ....ui.selectors.surfaces.story_viewer import STORY_SELECTORS


class StoryInteractionMixin(BaseAction):
    """Mixin: story ring clicks, highlight clicks, story likes and reactions."""

    STORY_REACTION_INDEXES = {
        "laugh": 0,
        "laughing": 0,
        "joy": 0,
        "surprise": 1,
        "wow": 1,
        "heart_eyes": 2,
        "love": 2,
        "cry": 3,
        "sad": 3,
        "clap": 4,
        "applause": 4,
        "fire": 5,
    }

    def _click_element_center(self, element, label: str) -> bool:
        """Click the center of a uiautomator element, falling back to element.click."""
        try:
            bounds = element.info.get('bounds', {}) if hasattr(element, 'info') else {}
            left = bounds.get('left', 0)
            right = bounds.get('right', 0)
            top = bounds.get('top', 0)
            bottom = bounds.get('bottom', 0)

            if right > left and bottom > top:
                self.device.click_coordinates((left + right) // 2, (top + bottom) // 2)
            else:
                element.click()

            self._human_like_delay('click')
            self.logger.debug(f"Clicked {label}")
            return True
        except Exception as e:
            self.logger.error(f"Error clicking {label}: {e}")
            return False

    def click_story_ring(self, story_index: int = 0) -> bool:
        """Open the active profile-avatar story ring (backward-compatible alias).

        A profile page exposes a single avatar ring, so `story_index` is ignored.
        Delegates to `click_profile_story_ring()`, which is scoped to the profile
        header avatar so highlights and the home feed tray are never mistaken for a
        watchable story. Use `click_highlight()` for highlights and
        `click_feed_story()` for the home tray when precision is needed.
        """
        return self.click_profile_story_ring()

    def click_feed_story(self, story_index: int = 0, skip_own_story: bool = True) -> bool:
        """Click a visible story bubble from the home feed tray.

        The home tray normally exposes the user's own story as the first item.
        `story_index=0` therefore means the first friend's story when
        `skip_own_story=True`.
        """
        try:
            elements = self.device.xpath(STORY_SELECTORS.feed_story_buttons).all()
            if not elements:
                elements = self.device.xpath(STORY_SELECTORS.feed_unseen_story_buttons).all()

            if not elements:
                self.logger.debug("No visible feed stories found")
                return False

            target_index = story_index + 1 if skip_own_story and len(elements) > 1 else story_index
            if target_index >= len(elements):
                self.logger.warning(f"Feed story index {story_index} out of bounds (visible: {len(elements)})")
                return False

            return self._click_element_center(elements[target_index], f"feed story #{story_index}")
        except Exception as e:
            self.logger.error(f"Error clicking feed story #{story_index}: {e}")
            return False

    def click_profile_story_ring(self) -> bool:
        """Click the current profile's active story ring, excluding highlights."""
        try:
            element = self.device.xpath(STORY_SELECTORS.profile_unseen_story_avatar).get()
            if not element:
                self.logger.debug("No unseen profile story avatar found")
                return False

            return self._click_element_center(element, "profile story ring")
        except Exception as e:
            self.logger.error(f"Error clicking profile story ring: {e}")
            return False

    def click_highlight(self, highlight_index: int = 0) -> bool:
        """Click a visible highlight bubble by horizontal index."""
        try:
            elements = self.device.xpath(STORY_SELECTORS.highlight_buttons).all()
            if not elements:
                self.logger.debug("No visible highlights found")
                return False
            if highlight_index >= len(elements):
                self.logger.warning(f"Highlight index {highlight_index} out of bounds (max: {len(elements) - 1})")
                return False

            return self._click_element_center(elements[highlight_index], f"highlight #{highlight_index}")
        except Exception as e:
            self.logger.error(f"Error clicking highlight #{highlight_index}: {e}")
            return False

    def _tray_y_ratio(self, recycler_selector, default_ratio: float) -> float:
        """Mid-row (as a fraction of screen height) of a horizontally scrollable tray, read from
        its recycler bounds — so the humanized horizontal swipe lands ON the tray, not mid-screen.
        Falls back to `default_ratio` when the tray bounds are unreadable."""
        try:
            tray = self.device.xpath(recycler_selector).get()
            if tray:
                bounds = tray.info.get('bounds', {})
                top, bottom = bounds.get('top', 0), bounds.get('bottom', 0)
                if bottom > top:
                    _, height = self.device.get_screen_size()
                    return ((top + bottom) / 2) / max(1, height)
        except Exception:
            pass
        return default_ratio

    def scroll_highlights_left(self) -> bool:
        """Swipe the highlights tray left to reveal highlights on the right (humanized horizontal
        swipe pinned to the tray row — was a fixed-coordinate swipe)."""
        try:
            y_ratio = self._tray_y_ratio(STORY_SELECTORS.highlight_recycler, 0.45)
            self.device.human_hswipe("left", y_ratio=y_ratio)
            self._human_like_delay('scroll')
            return True
        except Exception as e:
            self.logger.error(f"Error scrolling highlights tray: {e}")
            return False

    def scroll_feed_stories_left(self) -> bool:
        """Swipe the home story tray left to reveal more friends' stories (humanized horizontal
        swipe pinned to the top tray row — was a fixed-coordinate swipe)."""
        try:
            y_ratio = self._tray_y_ratio(STORY_SELECTORS.feed_story_recycler, 0.17)
            self.device.human_hswipe("left", y_ratio=y_ratio)
            self._human_like_delay('scroll')
            return True
        except Exception as e:
            self.logger.error(f"Error scrolling feed story tray: {e}")
            return False

    def click_story_like_button(self) -> bool:
        return self._find_and_click(STORY_SELECTORS.story_like_button, timeout=3)

    def like_story(self) -> bool:
        """Backward-compatible alias used by business story workflows."""
        return self.click_story_like_button()

    def open_story_reactions(self) -> bool:
        """Open the story reaction toolbar by clicking the message composer."""
        try:
            if self._is_element_present(STORY_SELECTORS.story_reaction_toolbar):
                return True

            if not self._find_and_click(STORY_SELECTORS.story_message_composer, timeout=3):
                self.logger.debug("Story message composer not found")
                return False

            return self._wait_for_element(STORY_SELECTORS.story_reaction_toolbar, timeout=3, silent=True)
        except Exception as e:
            self.logger.error(f"Error opening story reactions: {e}")
            return False

    def open_story_reply_composer(self) -> bool:
        """Focus the story reply text field (message composer) for typing a reply."""
        return self._find_and_click(STORY_SELECTORS.story_message_composer, timeout=3)

    def react_to_story(self, reaction: Optional[str] = None, emoji_index: Optional[int] = None) -> bool:
        """React to the current story using Instagram's 2x3 quick reaction grid.

        Known order from the dump:
        0 laugh, 1 surprise, 2 heart_eyes, 3 cry, 4 clap, 5 fire.
        """
        try:
            if not self.open_story_reactions():
                return False

            elements = self.device.xpath(STORY_SELECTORS.story_reaction_emojis).all()
            if not elements:
                self.logger.debug("No story reaction emojis found")
                return False

            index = emoji_index
            if index is None and reaction:
                index = self.STORY_REACTION_INDEXES.get(reaction.strip().lower())
            if index is None:
                index = 0

            if index < 0 or index >= len(elements):
                self.logger.warning(f"Story reaction index {index} out of bounds (visible: {len(elements)})")
                return False

            return self._click_element_center(elements[index], f"story reaction #{index}")
        except Exception as e:
            self.logger.error(f"Error reacting to story: {e}")
            return False

    def close_story(self) -> bool:
        """Close the story viewer with a swipe-down gesture (back press is unreliable).

        NOTE: deliberately kept on the reliable full-travel centre swipe (not device.human_scroll):
        this is a DISMISS, and a humanized down-swipe that samples a shorter travel / lower start
        could fail to trigger the viewer close and leave the bot stuck in the story. Humanizing it
        needs device QA to confirm the close still fires every time — tracked as a deferred follow-up.
        """
        try:
            width, height = self.device.get_screen_size()
            self.device.swipe_coordinates(
                width // 2, int(height * 0.30),
                width // 2, int(height * 0.92),
                duration=0.30,
            )
            self._human_like_delay('scroll')
            return True
        except Exception as e:
            self.logger.error(f"Error closing story: {e}")
            return False
