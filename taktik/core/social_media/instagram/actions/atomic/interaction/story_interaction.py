"""Story interaction actions (profile story ring, highlights, story like)."""

from ...core.base_action import BaseAction
from ....ui.selectors import STORY_SELECTORS


class StoryInteractionMixin(BaseAction):
    """Mixin: story ring clicks, highlight clicks, and story like button."""

    def click_story_ring(self, story_index: int = 0) -> bool:
        """Backward-compatible generic story click.

        Prefer `click_profile_story_ring()` for the active profile avatar and
        `click_highlight()` for highlights when the workflow needs precision.
        """
        self.logger.debug(f"Clicking story #{story_index}")

        story_elements = []
        for selector in self.story_selectors.story_ring_indicators if hasattr(self.story_selectors, 'story_ring_indicators') else [self.story_selectors.story_ring]:
            try:
                elements = self.device.xpath(selector)
                if elements and elements.exists:
                    story_elements = elements.all()
                    break
            except Exception:
                continue

        if not story_elements:
            self.logger.warning("No stories found")
            return False

        if story_index >= len(story_elements):
            self.logger.warning(f"Index {story_index} out of bounds (max: {len(story_elements) - 1})")
            return False

        try:
            story_elements[story_index].click()
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.error(f"Error clicking story: {e}")
            return False

    def click_profile_story_ring(self) -> bool:
        """Click the current profile's active story ring, excluding highlights."""
        try:
            element = self.device.xpath(STORY_SELECTORS.profile_unseen_story_avatar).get()
            if not element:
                self.logger.debug("No unseen profile story avatar found")
                return False

            bounds = element.info.get('bounds', {})
            left = bounds.get('left', 0)
            right = bounds.get('right', 0)
            top = bounds.get('top', 0)
            bottom = bounds.get('bottom', 0)
            if right <= left or bottom <= top:
                return False

            self.device.click_coordinates((left + right) // 2, (top + bottom) // 2)
            self._human_like_delay('click')
            return True
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

            elements[highlight_index].click()
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.error(f"Error clicking highlight #{highlight_index}: {e}")
            return False

    def scroll_highlights_left(self) -> bool:
        """Swipe the highlights tray left to reveal highlights on the right."""
        try:
            tray = self.device.xpath(STORY_SELECTORS.highlight_recycler).get()
            if tray:
                bounds = tray.info.get('bounds', {})
                left = bounds.get('left', 0)
                right = bounds.get('right', 0)
                top = bounds.get('top', 0)
                bottom = bounds.get('bottom', 0)
                if right > left and bottom > top:
                    y = (top + bottom) // 2
                    self.device.swipe_coordinates(
                        int(left + (right - left) * 0.85),
                        y,
                        int(left + (right - left) * 0.15),
                        y,
                        duration=0.35,
                    )
                    self._human_like_delay('scroll')
                    return True

            width, height = self.device.get_screen_size()
            y = int(height * 0.45)
            self.device.swipe_coordinates(int(width * 0.82), y, int(width * 0.18), y, duration=0.35)
            self._human_like_delay('scroll')
            return True
        except Exception as e:
            self.logger.error(f"Error scrolling highlights tray: {e}")
            return False

    def click_story_like_button(self) -> bool:
        return self._click_button(STORY_SELECTORS.story_like_button, "Story Like button", "heart", timeout=3)

    def like_story(self) -> bool:
        """Backward-compatible alias used by business story workflows."""
        return self.click_story_like_button()
