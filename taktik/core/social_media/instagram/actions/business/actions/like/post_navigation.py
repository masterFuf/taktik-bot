"""Post navigation helpers for the like workflow (open, next, return)."""

import time
from loguru import logger


class PostNavigationMixin:
    """Mixin providing post navigation methods.
    
    Must be used with a class that inherits from BaseBusinessAction
    (provides self.device, self.logger, self.post_selectors, self.detection_selectors, etc.)
    """
    
    def _open_first_post_of_profile(self) -> bool:
        try:
            self.logger.info("Opening first post of profile...")
            
            posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            # If no posts visible, try scrolling down slightly to reveal the grid
            # This can happen after follow when suggestions popup was hidden by scrolling up
            if not posts:
                self.logger.debug("No posts visible, scrolling down to reveal grid...")
                from ....core.device.facade import Direction
                self.device.swipe(Direction.UP, scale=0.3)  # UP = finger moves up = content goes DOWN
                time.sleep(0.5)
                posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            if not posts:
                # Try one more time with a bigger scroll
                self.logger.debug("Still no posts, trying bigger scroll...")
                from ....core.device.facade import Direction
                self.device.swipe(Direction.UP, scale=0.5)
                time.sleep(0.5)
                posts = self.device.xpath(self.detection_selectors.post_thumbnail_selectors[0]).all()
            
            if not posts:
                self.logger.error("No posts found in grid after scrolling")
                return False
            
            first_post = posts[0]
            first_post.click()
            self.logger.debug("Clicking on first post...")
            
            time.sleep(3)  # Increased from 2s to 3s for slower devices
            
            if self._is_in_post_view():
                self.logger.success("First post opened successfully")
                return True
            else:
                self.logger.error("Failed to open first post")
                return False
                
        except Exception as e:
            self.logger.error(f"Error opening first post: {e}")
            return False
    
    def _is_in_post_view(self) -> bool:
        try:
            # Use both post_view_indicators and post_detail_indicators for better detection
            post_indicators = self.post_selectors.post_view_indicators + self.post_selectors.post_detail_indicators
            
            for indicator in post_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.debug(f"Post view detected via: {indicator[:50]}...")
                    return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking post view: {e}")
            return False
    
    def _navigate_to_next_post_in_sequence(self) -> bool:
        try:
            self.logger.debug("Navigating to next post...")
            
            # Get screen dimensions for adaptive swipe coordinates
            width, height = self.device.get_screen_size()
            
            try:
                # Vertical scroll: center X, from 78% to 21% of height
                center_x = width // 2
                start_y = int(height * 0.78)
                end_y = int(height * 0.21)
                
                self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.25)
                time.sleep(2.0)
                
                if self._is_in_post_view():
                    self.logger.debug("Navigation successful via vertical scroll")
                    return True
            except Exception as e:
                self.logger.debug(f"Vertical scroll failed: {e}")
            
            try:
                # Horizontal swipe: from 74% to 19% of width, center Y
                start_x = int(width * 0.74)
                end_x = int(width * 0.19)
                center_y = height // 2
                
                self.device.swipe_coordinates(start_x, center_y, end_x, center_y, duration=0.3)
                time.sleep(1)
                
                if self._is_in_post_view():
                    self.logger.debug("Navigation successful via horizontal swipe")
                    return True
            except Exception as e:
                self.logger.debug(f"Horizontal swipe failed: {e}")
            
            try:
                next_button_selectors = self.post_selectors.next_post_button_selectors
                
                for selector in next_button_selectors:
                    if self.device.xpath(selector).exists():
                        self.device.xpath(selector).click()
                        time.sleep(1)
                        
                        if self._is_in_post_view():
                            self.logger.debug("Navigation successful via Next button")
                            return True
            except Exception as e:
                self.logger.debug(f"Next button failed: {e}")
            
            self.logger.warning("All navigation methods failed")
            return False
            
        except Exception as e:
            self.logger.error(f"Error navigating to next post: {e}")
            return False
    
    def _return_to_profile_from_post(self):
        try:
            self.logger.info("Returning to profile from post...")
            
            back_selectors = self.post_selectors.back_button_selectors
            
            for selector in back_selectors:
                if self.device.xpath(selector).exists:
                    self.device.xpath(selector).click()
                    time.sleep(1.5)
                    self.logger.debug("Returned via back button")
                    return
            
            # Adaptive swipe coordinates
            width, height = self.device.get_screen_size()
            center_x = width // 2
            start_y = int(height * 0.625)  # ~62.5% of height
            end_y = int(height * 0.21)     # ~21% of height
            
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, duration=0.5)
            time.sleep(1.5)
            self.logger.debug("Returned via downward swipe")
            
        except Exception as e:
            self.logger.error(f"Error returning to profile: {e}")
