"""Atomic click actions for TikTok.


This module aggregates VideoActions, PopupActions and adds profile + navigation
click helpers.  Existing code can continue to ``from ....atomic.click_actions import ClickActions``
and get every method via a single class.
"""

from loguru import logger

from taktik.core.social_media.tiktok.actions.atomic.interaction.video_actions import VideoActions
from taktik.core.social_media.tiktok.actions.atomic.interaction.popup_actions import PopupActions
from taktik.core.social_media.tiktok.ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.followers import FOLLOWERS_SELECTORS
from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import PROFILE_SELECTORS


class ClickActions(VideoActions, PopupActions):
    """Backward-compatible aggregate of all atomic click actions.
    
    Inherits video + popup actions and adds profile + navigation methods.
    Every action uses resource-id or content-desc based selectors,
    so they hold across resolutions.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-click-atomic")
        self.profile_selectors = PROFILE_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
    
    # === Profile Actions ===
    
    def click_message_button(self) -> bool:
        """Click Message button on profile."""
        self.logger.debug("💬 Clicking Message button")
        
        if self._find_and_click(PROFILE_SELECTORS.message_button, timeout=5):
            return True
        
        self.logger.warning("Message button not found")
        return False

    def open_profile_grid_post(self, index: int) -> bool:
        """Open the video at `index` (0-based) of the grid of the profile on screen.

        The cells are the clickable ones of `profile_post_item`: on 43.1.4, `:id/e52` also names
        the container of the whole page, which a list of every `e52` takes for its first cell. The
        tap aims only at the part of the cell that nothing floated over the grid covers (46.6.3:
        « Vient d'être vue », which scrolls the grid instead), and does not tap at all when that
        part is too small or cannot be read.
        """
        return self._find_and_click(
            FOLLOWERS_SELECTORS.profile_post_item,
            nth=index,
            timeout=2,
            keep_out=PROFILE_SELECTORS.just_watched_button,
        )

    # === Header Tabs (For You page) ===
    
    def click_for_you_tab(self) -> bool:
        """Click For You tab in header."""
        self.logger.debug("📱 Clicking For You tab")
        return self._find_and_click(self.navigation_selectors.for_you_tab, timeout=3)
