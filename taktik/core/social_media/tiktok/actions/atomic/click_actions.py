"""Atomic click actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

This module aggregates VideoActions, PopupActions and adds profile + navigation
click helpers.  Existing code can continue to ``from ...atomic.click_actions import ClickActions``
and get every method via a single class.
"""

from loguru import logger

from .video_actions import VideoActions
from .popup_actions import PopupActions
from ...ui.selectors import (
    PROFILE_SELECTORS, 
    NAVIGATION_SELECTORS,
)


class ClickActions(VideoActions, PopupActions):
    """Backward-compatible aggregate of all atomic click actions.
    
    Inherits video + popup actions and adds profile + navigation methods.
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc
    pour garantir la compatibilité multi-résolution.
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
    
    # === Header Tabs (For You page) ===
    
    def click_for_you_tab(self) -> bool:
        """Click For You tab in header."""
        self.logger.debug("📱 Clicking For You tab")
        return self._find_and_click(self.navigation_selectors.for_you_tab, timeout=3)

