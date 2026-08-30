"""Atomic navigation actions for TikTok.


This module aggregates SearchActions and adds bottom-nav, header-tab,
and go_back helpers.  Existing code can continue to
``from ...atomic.navigation_actions import NavigationActions``
and get every method via a single class.
"""

from loguru import logger

from .search_actions import SearchActions
from taktik.core.social_media.tiktok.services.navigation.reset import return_to_tiktok_shell
from ...ui.selectors.shell.navigation import NAVIGATION_SELECTORS


class NavigationActions(SearchActions):
    """Backward-compatible aggregate of all atomic navigation actions.
    
    Inherits search actions and adds bottom nav, header tabs, go_back, etc.
    Every action uses resource-id or content-desc based selectors,
    so they hold across resolutions.
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

        # The bar has to EXIST before a tab can be tapped. Every full-screen page — a new-followers
        # list, a follow list, a visited profile, a settings sub-screen — hides it, and the tap
        # then lands on nothing while the caller reads "the tab is gone". This is a no-op from the
        # feed, so it costs nothing on the common path. Measured three times on 2026-08-30: the
        # navigation reset left the app, profile navigation failed from the inbox, and the
        # new-followers welcome pass could not reopen the page it had just read.
        return_to_tiktok_shell(self.device, logger=self.logger)

        if self._find_and_click(self.navigation_selectors.home_tab, timeout=5):
            self._human_like_delay('navigation')
            self.logger.success("✅ Navigated to Home")
            return True

        # Fallback: the bottom nav bar can be hidden behind a fullscreen surface (a stuck
        # profile screen, a popup) — back out incrementally and stop as soon as we're home,
        # instead of giving up immediately (device: the hashtag workflow died here after a
        # failed profile-fetch tap left the app off the bottom nav; every later
        # navigate_to_home/open_search attempt then kept failing with no way to recover).
        self.logger.debug("Fallback: using back button (incremental, stop at home)")
        for _ in range(3):
            self._press_back()
            if self._element_exists(self.navigation_selectors.home_tab_selected, timeout=1):
                self.logger.success("✅ Navigated to Home (via back)")
                return True

        self.logger.warning("❌ Failed to navigate to Home")
        return False
    
    def navigate_to_inbox(self) -> bool:
        """Navigate to Inbox.
        
        Uses resource-id mkr with content-desc "Inbox".
        """
        self.logger.info("📥 Navigating to Inbox")
        
        # The bar has to EXIST before a tab can be tapped. Every full-screen page — a new-followers
        # list, a follow list, a visited profile, a settings sub-screen — hides it, and the tap
        # then lands on nothing while the caller reads "the tab is gone". This is a no-op from the
        # feed, so it costs nothing on the common path. Measured three times on 2026-08-30: the
        # navigation reset left the app, profile navigation failed from the inbox, and the
        # new-followers welcome pass could not reopen the page it had just read.
        return_to_tiktok_shell(self.device, logger=self.logger)

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
        
        # The bar has to EXIST before a tab can be tapped. Every full-screen page — a new-followers
        # list, a follow list, a visited profile, a settings sub-screen — hides it, and the tap
        # then lands on nothing while the caller reads "the tab is gone". This is a no-op from the
        # feed, so it costs nothing on the common path. Measured three times on 2026-08-30: the
        # navigation reset left the app, profile navigation failed from the inbox, and the
        # new-followers welcome pass could not reopen the page it had just read.
        return_to_tiktok_shell(self.device, logger=self.logger)

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
    
