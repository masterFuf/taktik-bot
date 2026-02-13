import time
import random
from typing import Optional
from loguru import logger

from ..common.detection import is_reel_post, is_likers_popup_open


class UIHelpers:        
    def __init__(self, automation):
        """
        Initialize UI helpers.
        
        Args:
            automation: Reference to InstagramAutomation instance
        """
        self.automation = automation
        self.device = automation.device
        self.logger = automation.logger
        self.POST_SELECTORS = None
        self.POPUP_SELECTORS = None
        
        # Import selectors
        try:
            from ...ui.selectors import POST_SELECTORS, POPUP_SELECTORS
            self.POST_SELECTORS = POST_SELECTORS
            self.POPUP_SELECTORS = POPUP_SELECTORS
        except ImportError:
            self.logger.warning("Could not import UI selectors")
    
    def _random_delay(self, min_delay: float = 0.5, max_delay: float = 1.0) -> None:
        """Add a random delay to simulate human behavior."""
        time.sleep(random.uniform(min_delay, max_delay))
    
    def _find_element(self, selectors: list) -> object:
        """Find first matching element from a list of xpath selectors."""
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element
            except:
                continue
        return None
    
    def _element_exists(self, selectors: list) -> bool:
        """Check if any element from selectors exists."""
        return self._find_element(selectors) is not None
    
    def is_current_post_reel(self) -> bool:
        return is_reel_post(self.device, self.logger)
    
    def has_likes_on_current_post(self) -> bool:
        try:
            if not self.POST_SELECTORS:
                return False
            
            if self._element_exists(self.POST_SELECTORS.automation_like_indicators):
                self.logger.debug("Likes detected via selector")
                return True
            
            return False
            
        except Exception as e:
            self.logger.debug(f"Error detecting likes: {e}")
            return False
    
    def scroll_to_next_post(self) -> bool:
        try:
            screen_size = self.device.window_size()
            start_y = int(screen_size[1] * 0.8)
            end_y = int(screen_size[1] * 0.2)
            center_x = screen_size[0] // 2
            
            self.device.swipe(center_x, start_y, center_x, end_y, duration=0.3)
            self._random_delay(0.5, 1.0)
            return True
            
        except Exception as e:
            self.logger.error(f"Error scrolling to next post: {e}")
            return False
    
    def open_likes_list(self) -> bool:
        try:
            if not self.POST_SELECTORS:
                return False
                
            for selector in self.POST_SELECTORS.automation_like_count_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.debug(f"Attempting to click like counter: {selector}")
                        element.click()
                        self._random_delay(1.0, 2.0)
                        
                        if self.is_likes_popup_open():
                            self.logger.info("✅ Likes list opened successfully")
                            return True
                        else:
                            self.logger.debug("Popup not detected after click")
                except Exception as e:
                    self.logger.debug(f"Error with selector {selector}: {e}")
                    continue
            
            self.logger.warning("❌ Cannot open likes list")
            return False
            
        except Exception as e:
            self.logger.error(f"Error opening likes list: {e}")
            return False
    
    def is_likes_popup_open(self) -> bool:
        return is_likers_popup_open(self.device, self.logger)
    
    def close_likes_popup(self) -> bool:
        try:
            if not self.POPUP_SELECTORS:
                return False
                
            for selector in self.POPUP_SELECTORS.close_popup_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        self.logger.debug(f"Closing popup via: {selector}")
                        element.click()
                        self._random_delay(0.5, 1.0)
                        return True
                except Exception as e:
                    self.logger.debug(f"Error closing with {selector}: {e}")
                    continue
            
            self.device.press("back")
            self._random_delay(0.5, 1.0)
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing popup: {e}")
            return False
    
    def follow_user(self, username: str) -> bool:
        try:
            follow_button = self.device(text="Follow")
            if follow_button.exists():
                follow_button.click()
                self._random_delay(1, 2)
                return True
            
            follow_button = self.device(text="Suivre")
            if follow_button.exists():
                follow_button.click()
                self._random_delay(1, 2)
                return True
            
            return False
        except Exception as e:
            self.logger.debug(f"Error following @{username}: {e}")
            return False
    
    def interact_with_likers(self, max_interactions: int, like_percentage: float, 
                            follow_percentage: float, filters: dict) -> int:
        try:
            interactions_count = 0
            usernames_seen = set()
            scroll_attempts = 0
            max_scroll_attempts = 10
            
            while interactions_count < max_interactions and scroll_attempts < max_scroll_attempts:
                usernames = self._extract_usernames_from_popup()
                
                if not usernames:
                    self.logger.debug("Aucun username trouvé, scroll...")
                    self._scroll_in_popup()
                    scroll_attempts += 1
                    self._random_delay(0.5, 1.0)
                    continue
                
                new_usernames = [u for u in usernames if u not in usernames_seen]
                
                if not new_usernames:
                    self.logger.debug("Pas de nouveaux usernames, scroll...")
                    self._scroll_in_popup()
                    scroll_attempts += 1
                    self._random_delay(0.5, 1.0)
                    continue
                
                for username in new_usernames:
                    if interactions_count >= max_interactions:
                        break
                    
                    usernames_seen.add(username)
                    
                    if filters:
                        # TODO: Implement filtering logic
                        pass
                    
                    if random.random() < like_percentage:
                        self.logger.info(f"❤️  Like pour @{username}")
                        interactions_count += 1
                    
                    if random.random() < follow_percentage:
                        if self.follow_user(username):
                            self.logger.info(f"➕ Follow @{username}")
                    
                    self._random_delay(1.0, 2.0)
                
                scroll_attempts = 0
            
            return interactions_count
            
        except Exception as e:
            self.logger.error(f"Error interacting with likers: {e}")
            return 0
    
    def _extract_usernames_from_popup(self) -> list:
        usernames = []
        try:
            if not hasattr(self, 'DETECTION_SELECTORS') or not self.DETECTION_SELECTORS:
                from ...ui.selectors import DETECTION_SELECTORS
                self.DETECTION_SELECTORS = DETECTION_SELECTORS
            
            for selector in self.DETECTION_SELECTORS.likers_list_username_selectors:
                elements = self.device.xpath(selector).all()
                for elem in elements:
                    text = elem.text
                    if text and text.startswith('@'):
                        username = text.replace('@', '').strip()
                        if username and username not in usernames:
                            usernames.append(username)
            
            return usernames
            
        except Exception as e:
            self.logger.debug(f"Error extracting usernames: {e}")
            return []
    
    def _scroll_in_popup(self):
        try:
            screen_size = self.device.window_size()
            start_y = int(screen_size[1] * 0.7)
            end_y = int(screen_size[1] * 0.3)
            center_x = screen_size[0] // 2
            
            self.device.swipe(center_x, start_y, center_x, end_y, duration=0.3)
            
        except Exception as e:
            self.logger.debug(f"Error scrolling popup: {e}")
