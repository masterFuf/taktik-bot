"""Atomic detection actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

This module aggregates VideoDetector and PopupDetector and adds
page-detection, error/state detection, and app-state helpers.
Existing code can continue to ``from ...atomic.detection_actions import DetectionActions``
and get every method via a single class.
"""

from loguru import logger

from .video_detector import VideoDetector
from .popup_detector import PopupDetector
from ...ui.selectors import (
    NAVIGATION_SELECTORS,
    INBOX_SELECTORS,
)


class DetectionActions(VideoDetector, PopupDetector):
    """Backward-compatible aggregate of all atomic detection actions.
    
    Inherits video + popup detectors and adds page/error/app-state detection.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-detection-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.inbox_selectors = INBOX_SELECTORS
    
    # === Page Detection ===
    
    def is_on_for_you_page(self) -> bool:
        """Check if currently on For You feed.
        
        Détecte via:
        - Tab "For You" sélectionné dans le header
        - Présence des boutons d'interaction vidéo
        """
        # Check if For You tab is visible and selected
        if self._element_exists(self.navigation_selectors.for_you_tab, timeout=2):
            # Also check for video interaction buttons
            if self._element_exists(self.video_selectors.like_button, timeout=1):
                return True
        
        # Fallback: check for home tab selected
        return self._element_exists(self.navigation_selectors.home_tab_selected, timeout=1)
    
    def is_on_inbox_page(self) -> bool:
        """Check if currently on Inbox page.
        
        Détecte via:
        - Titre "Inbox"
        - Présence des sections de notification
        """
        if self._element_exists(self.inbox_selectors.inbox_title, timeout=2):
            return True
        
        # Check for inbox tab selected
        return self._element_exists(self.navigation_selectors.inbox_tab_selected, timeout=1)
