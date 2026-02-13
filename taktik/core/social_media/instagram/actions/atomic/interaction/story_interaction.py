"""Story interaction actions (story ring click, story like)."""

from typing import Optional
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import BUTTON_SELECTORS, STORY_SELECTORS


class StoryInteractionMixin(BaseAction):
    """Mixin: story ring clicks and story like button."""

    def click_story_ring(self, story_index: int = 0) -> bool:
        self.logger.debug(f"📱 Clicking story #{story_index}")
        
        # Trouver toutes les stories
        story_elements = []
        for selector in self.story_selectors.story_ring_indicators if hasattr(self.story_selectors, 'story_ring_indicators') else [self.story_selectors.story_ring]:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    story_elements = elements.all()
                    break
            except Exception:
                continue
        
        if not story_elements:
            self.logger.warning("No stories found")
            return False
        
        if story_index >= len(story_elements):
            self.logger.warning(f"Index {story_index} out of bounds (max: {len(story_elements)-1})")
            return False
        
        try:
            story_elements[story_index].click()
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.error(f"Error clicking story: {e}")
            return False

    def click_story_like_button(self) -> bool:
        return self._click_button(self.selectors.like_button, "Story Like button", "❤️", timeout=3)
