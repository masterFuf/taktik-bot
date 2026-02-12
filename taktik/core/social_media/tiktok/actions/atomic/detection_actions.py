"""Atomic detection actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

This module aggregates VideoDetector and PopupDetector and adds
page-detection, error/state detection, and app-state helpers.
Existing code can continue to ``from ...atomic.detection_actions import DetectionActions``
and get every method via a single class.
"""

from typing import Tuple
from loguru import logger

from .video_detector import VideoDetector
from .popup_detector import PopupDetector
from ...ui.selectors import (
    NAVIGATION_SELECTORS,
    INBOX_SELECTORS,
    DETECTION_SELECTORS,
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
        self.detection_selectors = DETECTION_SELECTORS
    
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
        home_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mkq"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Home"][@selected="true"]',
        ]
        return self._element_exists(home_selected, timeout=1)
    
    def is_on_profile_page(self) -> bool:
        """Check if currently on a profile page.
        
        Détecte via:
        - Présence du display name (qf8) ou username (qh5)
        - Présence des compteurs (following/followers/likes)
        """
        # Check for profile-specific elements
        if self._element_exists(self.profile_selectors.display_name, timeout=2):
            return True
        
        if self._element_exists(self.profile_selectors.username, timeout=2):
            return True
        
        # Check for profile tab selected
        profile_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mks"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Profile"][@selected="true"]',
        ]
        return self._element_exists(profile_selected, timeout=1)
    
    def is_on_inbox_page(self) -> bool:
        """Check if currently on Inbox page.
        
        Détecte via:
        - Titre "Inbox"
        - Présence des sections de notification
        """
        if self._element_exists(self.inbox_selectors.inbox_title, timeout=2):
            return True
        
        # Check for inbox tab selected
        inbox_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mkr"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Inbox"][@selected="true"]',
        ]
        return self._element_exists(inbox_selected, timeout=1)
    
    def is_on_friends_page(self) -> bool:
        """Check if currently on Friends page."""
        friends_selected = [
            '//*[@resource-id="com.zhiliaoapp.musically:id/mkp"][@selected="true"]',
            '//android.widget.FrameLayout[@content-desc="Friends"][@selected="true"]',
        ]
        return self._element_exists(friends_selected, timeout=1)
    
    def get_current_page(self) -> str:
        """Detect current page.
        
        Returns:
            str: 'for_you', 'following', 'profile', 'inbox', 'friends', 'search', 'unknown'
        """
        if self.is_on_for_you_page():
            return 'for_you'
        
        if self.is_on_profile_page():
            return 'profile'
        
        if self.is_on_inbox_page():
            return 'inbox'
        
        if self.is_on_friends_page():
            return 'friends'
        
        # Check for Following feed
        following_tab = [
            '//*[@content-desc="Following"][@selected="true"]',
            '//*[@text="Following"][@selected="true"]',
        ]
        if self._element_exists(following_tab, timeout=1):
            return 'following'
        
        # Check for search page
        if self._element_exists(['//*[contains(@resource-id, "search")]'], timeout=1):
            return 'search'
        
        return 'unknown'
    
    # === Error & State Detection ===
    
    def has_error(self) -> bool:
        """Check if there's an error message on screen."""
        return self._element_exists(self.detection_selectors.error_message, timeout=1)
    
    def has_network_error(self) -> bool:
        """Check if there's a network error."""
        return self._element_exists(self.detection_selectors.network_error, timeout=1)
    
    def has_rate_limit(self) -> bool:
        """Check if rate limited (soft ban indicator)."""
        return self._element_exists(self.detection_selectors.rate_limit, timeout=1)
    
    def detect_problematic_state(self) -> Tuple[bool, str]:
        """Detect if in a problematic state.
        
        Returns:
            Tuple[bool, str]: (is_problematic, reason)
        """
        if self.has_rate_limit():
            return True, "rate_limit"
        
        if self.has_network_error():
            return True, "network_error"
        
        if self.has_error():
            return True, "error"
        
        return False, "ok"
    
    # === TikTok App State ===
    
    def is_tiktok_running(self) -> bool:
        """Check if TikTok app is running and visible."""
        # Check for any TikTok-specific element
        tiktok_indicators = [
            '//*[@package="com.zhiliaoapp.musically"]',
            '//*[@resource-id="com.zhiliaoapp.musically:id/mky"]',  # Bottom nav
        ]
        return self._element_exists(tiktok_indicators, timeout=2)
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in.
        
        If on profile page and can see profile info, user is logged in.
        """
        # Navigate to profile and check
        if self._element_exists(self.navigation_selectors.profile_tab, timeout=2):
            # Profile tab exists, likely logged in
            return True
        return False
