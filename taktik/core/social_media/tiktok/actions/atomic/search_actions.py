"""Atomic search actions for TikTok.

Extracted from navigation_actions.py — contains search-specific navigation:
open search, type query, submit, click tabs/results, navigate to user profile,
search hashtag.

"""

from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors.shell.navigation import NAVIGATION_SELECTORS
from ...ui.selectors.surfaces.search import SEARCH_SELECTORS


class SearchActions(BaseAction):
    """Low-level search and search-result navigation actions for TikTok."""

    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="tiktok-search-atomic")
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.search_selectors = SEARCH_SELECTORS

    # === Search Opening ===

    def open_search(self) -> bool:
        """Open search page from For You page.
        
        Clicks on the search icon (magnifying glass) in the header.
        Uses resource-id irz with content-desc "Search".
        """
        self.logger.info("🔍 Opening search")
        
        try:
            # Try navigation selectors first
            if self._find_and_click(self.navigation_selectors.search_button, timeout=3):
                self._human_like_delay('navigation')
                self.logger.success("✅ Search page opened")
                return True
            
            # Try search selectors (search_icon)
            if self._find_and_click(self.search_selectors.search_icon, timeout=3):
                self._human_like_delay('navigation')
                self.logger.success("✅ Search page opened via search_icon")
                return True
            
            self.logger.warning("❌ Search button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening search: {e}")
            return False

    def search_and_submit(self, query: str) -> bool:
        """Type a search query and submit it.
        
        Args:
            query: The search query to type
            
        Returns:
            True if search was submitted successfully
        """
        self.logger.info(f"🔍 Searching for: {query}")
        
        try:
            # Click on search input field
            if not self._find_and_click(self.search_selectors.search_input, timeout=5):
                self.logger.warning("Search input not found")
                return False
            
            self._human_like_delay('click')
            
            # Type the search query
            if not self._input_text(self.search_selectors.search_input, query, clear_first=True):
                self.logger.warning("Failed to input search query")
                return False
            
            self._human_like_delay('typing')
            
            # Click the Search submit button
            if self._find_and_click(self.search_selectors.search_submit_button, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success(f"✅ Search submitted for: {query}")
                return True
            
            # Fallback: press Enter key
            self._press_enter()
            self._human_like_delay('navigation')
            self.logger.success(f"✅ Search submitted via Enter for: {query}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error searching for {query}: {e}")
            return False

    # === Search Result Tabs ===

    def click_videos_tab(self) -> bool:
        """Click on Videos tab in search results."""
        self.logger.info("🎬 Clicking Videos tab")
        
        if self._find_and_click(self.search_selectors.videos_tab, timeout=5):
            self._human_like_delay('click')
            self.logger.success("✅ Clicked Videos tab")
            return True
        
        self.logger.warning("❌ Videos tab not found")
        return False

    def click_first_video_result(self) -> bool:
        """Click on the first video in search results.
        
        This opens the video in full-screen mode for scrolling.
        """
        self.logger.info("🎬 Clicking first video result")
        
        try:
            # Try clicking on video container
            if self._find_and_click(self.search_selectors.video_result_container, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success("✅ Clicked first video result")
                return True
            
            # Fallback: click on video thumbnail
            if self._find_and_click(self.search_selectors.video_thumbnail, timeout=5):
                self._human_like_delay('navigation')
                self.logger.success("✅ Clicked video thumbnail")
                return True
            
            self.logger.warning("❌ No video result found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking video result: {e}")
            return False

    # === Composite Search Flows ===

    def search_and_open_videos(self, query: str) -> bool:
        """Search for a query and open the first video result.
        
        This is the main method for the Target workflow:
        1. Open search from For You page
        2. Type and submit search query
        3. Click on Videos tab
        4. Click on first video to start scrolling
        
        Args:
            query: The search query (username, hashtag, keyword)
            
        Returns:
            True if successfully opened a video from search results
        """
        self.logger.info(f"🔍 Searching and opening videos for: {query}")
        
        try:
            # Try to open search directly first (we might already be on For You page)
            if not self.open_search():
                # If that fails, try navigating to home first
                self.logger.info("🏠 Search button not found, trying to navigate to Home first")
                if self._find_and_click(self.navigation_selectors.home_tab, timeout=5):
                    self._human_like_delay('navigation')
                
                # Try opening search again
                if not self.open_search():
                    self.logger.error("❌ Could not open search")
                    return False
            
            # Search and submit
            if not self.search_and_submit(query):
                return False
            
            self._human_like_delay('navigation')
            
            # Click on Videos tab to filter to videos only
            if not self.click_videos_tab():
                self.logger.warning("Could not click Videos tab, trying to find videos anyway")
            
            self._human_like_delay('click')
            
            # Click on first video result
            if self.click_first_video_result():
                self.logger.success(f"✅ Opened video from search: {query}")
                return True
            
            self.logger.warning(f"❌ No videos found for: {query}")
            return False
            
        except Exception as e:
            self.logger.error(f"Error in search_and_open_videos: {e}")
            return False

    def navigate_to_user_profile(self, username: str) -> bool:
        """Navigate to specific user's profile via search."""
        self.logger.info(f"👤 Navigating to @{username}'s profile")
        
        try:
            # First go to home, then click search
            if self._find_and_click(self.navigation_selectors.home_tab, timeout=5):
                self._human_like_delay('navigation')
            
            # Open search page
            if not self.open_search():
                return False
            
            # Search for the username
            if not self.search_and_submit(username):
                return False
            
            self._human_like_delay('navigation')
            
            # Click on Users tab to filter results
            if self._element_exists(self.search_selectors.users_tab, timeout=3):
                self._find_and_click(self.search_selectors.users_tab, timeout=3)
                self._human_like_delay('click')
            
            # The row of the user actually asked for. The Users tab also lists fan accounts
            # carrying that handle as their DISPLAY name, so "the first row" is not the same
            # thing as "the right person".
            first_result_selectors = self.search_selectors.user_result_selectors_for_username(username)

            if self._find_and_click(first_result_selectors, timeout=5):
                self._human_like_delay('navigation')
                return self._landed_on_profile_of(username)

            self.logger.warning(f"❌ Failed to find @{username} in search results")
            return False

        except Exception as e:
            self.logger.error(f"Error navigating to @{username}: {e}")
            return False

    def _landed_on_profile_of(self, username: str, *, settle_timeout: float = 5.0) -> bool:
        """Did the tap actually open THIS person's profile?

        Reporting success on the click alone is what lets a workflow interact with the wrong
        account and record it under the right one. So the answer comes from the screen, in two
        steps that answer two different questions.

        First: are we on a profile at all? Measured on 43.1.4, a search can land on something
        that is not a profile — an interstitial, a blocked-term safety screen — and stay there.
        An unreadable handle there is not a slow header, it is the wrong screen, and the whole
        point of this check is to refuse it.

        Then, and only on a profile: is it the right one? A handle that cannot be read on a
        screen that IS a profile is let through, because TikTok sometimes renders the header a
        beat after the grid and refusing there would turn a slow screen into a failed target.
        Same two steps as the Instagram navigation.
        """
        from taktik.core.social_media.tiktok.services.profile.username import (
            UNKNOWN_USERNAME,
            clean_profile_username,
            get_current_profile_username,
        )
        from taktik.core.social_media.tiktok.ui.selectors.surfaces.profile import (
            PROFILE_SELECTORS,
        )

        # Polled rather than read once: the profile screen is what we are waiting FOR, and a
        # single read a beat too early would refuse a profile that is simply still drawing.
        if not self._element_exists(PROFILE_SELECTORS.profile_page_indicator, timeout=settle_timeout):
            self.logger.error(
                f"❌ Looking for @{username}, but this screen is not a profile — not interacting"
            )
            return False

        expected = clean_profile_username(username).lower()
        landed = get_current_profile_username(self.device)

        if landed == UNKNOWN_USERNAME or not landed:
            self.logger.warning(
                f"⚠️ On a profile but could not read its handle after opening @{username} — continuing"
            )
            return True

        if clean_profile_username(landed).lower() != expected:
            self.logger.error(
                f"❌ Opened @{landed} while looking for @{username} — wrong profile, not interacting"
            )
            return False

        self.logger.success(f"✅ Navigated to @{username}'s profile")
        return True
