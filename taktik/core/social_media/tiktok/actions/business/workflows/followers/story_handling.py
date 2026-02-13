"""Story handling mixin for the TikTok Followers workflow.

Handles accidental story landings: watches, optionally likes,
then navigates to the profile.
"""

import time
import random


class StoryHandlingMixin:
    """Methods for handling TikTok story views during the followers workflow."""

    def _handle_story_view(self):
        """Handle when we accidentally land on a story instead of profile.
        
        Strategy:
        1. Watch the story briefly (simulates human behavior)
        2. Optionally like the story
        3. Click on the username to go to the profile
        
        This turns an "accident" into an opportunity for engagement!
        """
        try:
            self.logger.info("📖 Handling story view...")
            
            # Watch story for a bit (human-like behavior)
            watch_time = random.uniform(3.0, 6.0)
            self.logger.debug(f"Watching story for {watch_time:.1f}s")
            time.sleep(watch_time)
            
            # Optionally like the story (use story_like_probability from config)
            if random.random() < self.config.story_like_probability:
                if self.stats.likes < self.config.max_likes_per_session:
                    if self._try_like_story():
                        self.stats.likes += 1
                        self._send_action('like_story', self._current_profile_username or 'unknown')
                        self._send_stats_update()
            
            # Now click on the username to go to the profile
            from .....ui.selectors import PROFILE_SELECTORS
            
            for selector in PROFILE_SELECTORS.story_username:
                elem = self.device.xpath(selector)
                if elem.exists:
                    self.logger.debug("Clicking username to go to profile from story")
                    elem.click()
                    time.sleep(1.5)  # Wait for profile to load
                    
                    # Verify we're now on the profile
                    if self._is_on_profile_page():
                        self.logger.info("✅ Successfully navigated from story to profile")
                        return
                    break
            
            # Fallback: if clicking username didn't work, close the story
            self.logger.debug("Username click didn't work, closing story...")
            close_btn = self.device.xpath(PROFILE_SELECTORS.story_close_button[0])
            if close_btn.exists:
                close_btn.click()
                time.sleep(1.0)
            else:
                # Last resort: press back
                self._go_back()
                time.sleep(1.0)
                
        except Exception as e:
            self.logger.debug(f"Error handling story view: {e}")
            # Try to recover by pressing back
            self._go_back()
            time.sleep(1.0)
    
    def _try_like_story(self) -> bool:
        """Try to like the current story."""
        try:
            # Story like button uses same selectors as video like
            for selector in self.video_selectors.like_button_unliked:
                elem = self.device.xpath(selector)
                if elem.exists:
                    elem.click()
                    self.logger.info("❤️ Liked story")
                    self._human_delay()
                    return True
        except Exception as e:
            self.logger.debug(f"Error liking story: {e}")
        return False
