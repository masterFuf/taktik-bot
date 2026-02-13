"""Atomic navigation actions for TikTok.

Dernière mise à jour: 7 janvier 2026
Basé sur les UI dumps réels de TikTok.

This module aggregates SearchActions and adds bottom-nav, header-tab,
and go_back helpers.  Existing code can continue to
``from ...atomic.navigation_actions import NavigationActions``
and get every method via a single class.
"""

from loguru import logger

from .search_actions import SearchActions
from ...ui.selectors import NAVIGATION_SELECTORS


class NavigationActions(SearchActions):
    """Backward-compatible aggregate of all atomic navigation actions.
    
    Inherits search actions and adds bottom nav, header tabs, go_back, etc.
    Toutes les actions utilisent des sélecteurs basés sur resource-id/content-desc
    pour garantir la compatibilité multi-résolution.
    """
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-navigation-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
    
    # === Bottom Navigation Bar ===
    
    def navigate_to_home(self) -> bool:
        """Navigate to Home feed (For You).
        
        Uses resource-id mkq with content-desc "Home".
        """
        self.logger.info("🏠 Navigating to Home")
        
        if self._find_and_click(self.navigation_selectors.home_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Home")
            return True
        
        self.logger.warning("❌ Failed to navigate to Home")
        return False
    
    def navigate_to_inbox(self) -> bool:
        """Navigate to Inbox.
        
        Uses resource-id mkr with content-desc "Inbox".
        """
        self.logger.info("📥 Navigating to Inbox")
        
        if self._find_and_click(self.navigation_selectors.inbox_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Inbox")
            return True
        
        self.logger.warning("❌ Failed to navigate to Inbox")
        return False
    
    def navigate_to_profile(self) -> bool:
        """Navigate to own profile.
        
        Uses resource-id mks with content-desc "Profile".
        """
        self.logger.info("👤 Navigating to Profile")
        
        if self._find_and_click(self.navigation_selectors.profile_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Profile")
            return True
        
        self.logger.warning("❌ Failed to navigate to Profile")
        return False
    
    # === Back / Author Profile ===
    
    def go_back(self) -> bool:
        """Go back to previous screen."""
        self.logger.debug("⬅️ Going back")
        
        try:
            # Try UI back button first
            if self._find_and_click(self.navigation_selectors.back_button, timeout=2):
                self._human_like_delay('navigation')
                return True
            
            # Fallback: hardware back button
            self._press_back()
            return True
            
        except Exception as e:
            self.logger.error(f"Error going back: {e}")
            return False
    
