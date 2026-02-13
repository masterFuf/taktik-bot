"""Navigation mixin for the TikTok Followers workflow.

Handles navigating to the target user's followers list,
returning to the list after profile visits, and recovery
when navigation fails.
"""

import time


class NavigationMixin:
    """Methods for navigating to/from the followers list."""

    def _navigate_to_followers_list(self) -> bool:
        """Navigate to the followers list of the target user."""
        self.logger.info(f"🔍 Navigating to followers of: {self.config.search_query}")
        
        try:
            # Search for the target user (with inbox recovery)
            if not self._search_for_target():
                return False
            
            # Dismiss any notification banner that might interfere
            self.click.dismiss_notification_banner()
            
            # Click on Users tab
            if not self._click_users_tab():
                # Check if a notification banner sent us to inbox
                if self._check_and_recover_from_inbox():
                    # Retry from search
                    if not self._search_for_target():
                        return False
                    self.click.dismiss_notification_banner()
                    self._click_users_tab()  # best-effort retry
                else:
                    self.logger.warning("Could not click Users tab, trying to find users anyway")
            
            self._human_delay()
            
            # Click on first user result (the target user)
            if not self._click_first_user():
                # Check if we ended up on inbox again
                if self._check_and_recover_from_inbox():
                    if not self._search_for_target():
                        return False
                    self.click.dismiss_notification_banner()
                    self._click_users_tab()
                    self._human_delay()
                    if not self._click_first_user():
                        self.logger.error("Failed to click on target user after inbox recovery")
                        return False
                else:
                    self.logger.error("Failed to click on target user")
                    return False
            
            self._human_delay()
            
            # Click on Followers counter to open followers list
            if not self._click_followers_counter():
                self.logger.error("Failed to open followers list")
                return False
            
            self._human_delay()
            
            self.logger.success("✅ Navigated to followers list")
            return True
            
        except Exception as e:
            self.logger.error(f"Error navigating to followers list: {e}")
            return False
    
    def _search_for_target(self) -> bool:
        """Open search, type the target query, and submit. Handles inbox recovery."""
        if not self.navigation.open_search():
            self.logger.error("Failed to open search")
            return False
        
        self._human_delay()
        
        if not self.navigation.search_and_submit(self.config.search_query):
            self.logger.error("Failed to submit search")
            return False
        
        self._human_delay()
        
        # Check if we accidentally landed on Inbox page (notification clicked)
        if self.detection.is_on_inbox_page():
            self.logger.warning("⚠️ Accidentally on Inbox page after search, going back...")
            self.click.escape_inbox_page()
            time.sleep(1)
            if not self.navigation.open_search():
                return False
            self._human_delay()
            if not self.navigation.search_and_submit(self.config.search_query):
                return False
            self._human_delay()
        
        return True
    
    def _check_and_recover_from_inbox(self) -> bool:
        """Check if we're on the inbox page and recover if so.
        
        Returns:
            True if we were on inbox and successfully recovered, False if not on inbox.
        """
        if not self.detection.is_on_inbox_page():
            return False
        
        self.logger.warning("⚠️ Notification banner sent us to Inbox, recovering...")
        self.click.escape_inbox_page()
        time.sleep(1)
        # Press back again in case we're in a conversation
        if self.detection.is_on_inbox_page():
            self.device.press("back")
            time.sleep(1)
        return True
    
    def _click_users_tab(self) -> bool:
        """Click on the Users tab in search results."""
        self.logger.debug("Clicking Users tab")
        selectors = self.followers_selectors.users_tab
        return self.click._find_and_click(selectors, timeout=5)
    
    def _click_first_user(self) -> bool:
        """Click on the first user in search results."""
        self.logger.debug("Clicking first user result")
        selectors = self.followers_selectors.first_user_result
        if self.click._find_and_click(selectors, timeout=5):
            return True
        selectors = self.followers_selectors.user_search_item
        return self.click._find_and_click(selectors, timeout=5)
    
    def _click_followers_counter(self) -> bool:
        """Click on the Followers counter to open followers list.
        
        Also extracts and stores the followers count for smart scroll logic.
        """
        self.logger.debug("Clicking Followers counter")
        selectors = self.followers_selectors.followers_counter
        
        # Try to extract followers count before clicking
        try:
            for selector in selectors:
                element = self.device.xpath(selector)
                if element and element.exists:
                    # Try to get the text which contains the count
                    text = element.get_text() or ''
                    # Parse count from text like "267 Followers" or "1.2K Followers"
                    count = self._parse_followers_count(text)
                    if count > 0:
                        self._target_followers_count = count
                        self.logger.info(f"📊 Target has {count} followers")
                        break
        except Exception as e:
            self.logger.debug(f"Could not extract followers count: {e}")
        
        # Get count of already visited followers for this target
        if self._account_id and self.config.search_query:
            self._already_visited_count = self._db.count_tiktok_interactions_for_target(
                self._account_id, 
                self.config.search_query,
                hours=168  # 7 days
            )
            self.logger.info(f"📊 Already visited {self._already_visited_count} followers of @{self.config.search_query}")
        
        return self.click._find_and_click(selectors, timeout=5)
    
    @staticmethod
    def _parse_followers_count(text: str) -> int:
        """Parse followers count from text like '267 Followers', '1.2K', '1M'."""
        if not text:
            return 0
        from .....core.utils import parse_count
        # Remove "Followers"/"Follower" label before parsing
        cleaned = text.lower().replace('followers', '').replace('follower', '').strip()
        return parse_count(cleaned)

    def _safe_return_to_followers_list(self) -> bool:
        """Safely return to followers list with page verification.
        
        After interacting with videos, we need to:
        1. Press back to exit video → should land on profile page
        2. Press back again → should land on followers list
        
        Also handles edge cases like being on a story page.
        
        Returns:
            True if successfully returned to followers list, False otherwise.
        """
        max_attempts = 5  # Increased from 3 to handle edge cases
        
        for attempt in range(max_attempts):
            self.logger.debug(f"Return to followers list attempt {attempt + 1}/{max_attempts}")
            time.sleep(0.5)  # Small delay to let UI settle
            
            # Check current page state
            if self._is_on_followers_list():
                self.logger.debug("✅ Already on followers list")
                return True
            
            if self._is_on_story_page():
                # We're on a story page, close it first
                self.logger.debug("📖 On story page, closing story...")
                from .....ui.selectors import PROFILE_SELECTORS
                close_btn = self.device.xpath(PROFILE_SELECTORS.story_close_button[0])
                if close_btn.exists:
                    close_btn.click()
                    time.sleep(1.0)
                else:
                    self._go_back()
                    time.sleep(1.0)
                continue  # Re-check state after closing story
            
            if self._is_on_video_page():
                # We're on video page, need to go back to profile first
                self.logger.debug("📹 On video page, pressing back to profile...")
                self._go_back()
                time.sleep(1.0)
                continue  # Re-check state after back
            
            if self._is_on_profile_page():
                # We're on profile page, need to go back to followers list
                self.logger.debug("👤 On profile page, pressing back to followers list...")
                self._go_back()
                time.sleep(1.0)
                
                # Verify we landed on followers list
                if self._is_on_followers_list():
                    self.logger.debug("✅ Successfully returned to followers list")
                    return True
                else:
                    self.logger.debug("⚠️ Did not land on followers list after back from profile")
                    continue
            
            # Unknown state, try pressing back
            self.logger.debug("❓ Unknown page state, pressing back...")
            self._go_back()
            time.sleep(1.0)
        
        self.logger.warning("❌ Failed to return to followers list after max attempts")
        return False
    
    def _recover_to_followers_list(self) -> bool:
        """Recovery procedure: restart TikTok and navigate back to followers list.
        
        This is called when normal navigation fails. We:
        1. Restart TikTok app
        2. Navigate to the target user's followers list
        3. Since we skip already-interacted profiles, we'll resume where we left off
        
        Returns:
            True if recovery successful, False otherwise.
        """
        self.logger.info("🔄 Starting recovery procedure...")
        
        try:
            # Restart TikTok
            self.logger.info("🔄 Restarting TikTok...")
            self.device.app_stop('com.zhiliaoapp.musically')
            time.sleep(1)
            self.device.app_start('com.zhiliaoapp.musically')
            time.sleep(4)  # Wait for app to fully load
            
            # Navigate back to followers list
            self.logger.info(f"🔄 Navigating back to followers of: {self.config.search_query}")
            if self._navigate_to_followers_list():
                self.logger.info("✅ Recovery successful - back on followers list")
                return True
            else:
                self.logger.error("❌ Recovery failed - could not navigate to followers list")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Recovery error: {e}")
            return False
    
    def _go_back(self):
        """Press back button to return to previous screen.
        
        Prioritizes in-app back button (for phones without system back button),
        falls back to system back if not found.
        """
        try:
            if self.click._find_and_click(self.followers_selectors.back_button, timeout=2):
                time.sleep(0.5)
                return
            
            # Fallback: system back button
            self.device.press("back")
            time.sleep(0.5)
        except Exception as e:
            self.logger.debug(f"Error going back: {e}")
            self.device.press("back")
    
    def _scroll_followers_list(self):
        """Scroll the followers list to load more."""
        self.scroll.scroll_search_results(direction='down')
        time.sleep(0.5)
