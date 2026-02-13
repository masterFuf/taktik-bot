"""Screen state detection, error detection, and popup handling."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS, POST_SELECTORS


class ScreenDetectionMixin(BaseAction):
    """Mixin: detect current screen state, errors, rate limits, popups."""

    def _detect_element(self, selectors, element_name: str, log_found: bool = False) -> bool:
        """
        Generic method to detect if an element is present.
        
        Args:
            selectors: Selector or list of selectors
            element_name: Name for logging
            log_found: Whether to log when found
            
        Returns:
            True if element found, False otherwise
        """
        self.logger.debug(f"Detecting {element_name}")
        is_present = self._is_element_present(selectors)
        
        if log_found and is_present:
            self.logger.debug(f"✅ {element_name} detected")
        elif log_found:
            self.logger.debug(f"❌ {element_name} not found")
            
        return is_present

    # === Screen state ===

    def is_on_home_screen(self) -> bool:
        return self._detect_element(self.detection_selectors.home_screen_indicators, "Home screen")
    
    def is_on_search_screen(self) -> bool:
        return self._detect_element(self.detection_selectors.search_screen_indicators, "Search screen")
    
    def is_on_profile_screen(self) -> bool:
        is_profile = self._is_element_present(self.detection_selectors.profile_screen_indicators)
        if is_profile:
            self.logger.debug("✅ Profile screen detected")
        else:
            self.logger.debug("❌ Not on profile screen")
        
        return is_profile
    
    def is_on_own_profile(self) -> bool:
        if not self.is_on_profile_screen():
            self.logger.debug("❌ Not on profile screen")
            return False
        
        has_edit_profile = self._is_element_present(self.detection_selectors.own_profile_indicators)
        is_own_profile = has_edit_profile
        
        self.logger.debug(f"Profile detection - Edit profile: {has_edit_profile}")
        
        if is_own_profile:
            self.logger.debug("✅ Confirmed: on own profile")
        else:
            self.logger.debug("❌ Not on own profile")
            
        return is_own_profile

    def is_on_post_screen(self) -> bool:
        return self._detect_element(self.detection_selectors.post_screen_indicators, "Post screen")
    
    def is_reel_post(self) -> bool:
        return self._detect_element(self.detection_selectors.reel_indicators, "Reel post")

    def is_post_grid_visible(self) -> bool:
        return self._detect_element(self.detection_selectors.post_grid_visibility_indicators, "Post grid")

    def is_loading_spinner_visible(self) -> bool:
        """
        Détecte si un spinner de chargement est visible (Instagram charge du contenu).
        """
        return self._detect_element(
            self.detection_selectors.loading_spinner_indicators,
            "Loading spinner"
        )

    # === Error and rate limit detection ===

    def detect_error_messages(self) -> List[str]:
        errors = []
        for selector in self.detection_selectors.error_message_indicators:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        error_text = element.get_text()
                        if error_text and error_text not in errors:
                            errors.append(error_text)
            except Exception:
                continue
        
        if errors:
            self.logger.warning(f"{len(errors)} error messages detected")
        
        return errors
    
    def is_rate_limited(self) -> bool:
        is_limited = self._detect_element(self.detection_selectors.rate_limit_indicators, "Rate limit")
        if is_limited:
            self.logger.warning("Rate limit detected!")
        return is_limited
    
    def is_login_required(self) -> bool:
        return self._detect_element(self.detection_selectors.login_required_indicators, "Login required")
    
    def detect_popup_or_modal(self) -> Optional[str]:
        for popup_type, selector in self.detection_selectors.popup_types.items():
            if self._is_element_present([selector]):
                self.logger.debug(f"Popup detected: {popup_type}")
                return popup_type
        
        return None

    # === Aggregate state ===

    def get_screen_state_summary(self) -> Dict[str, Any]:
        return {
            'is_home': self.is_on_home_screen(),
            'is_search': self.is_on_search_screen(),
            'is_profile': self.is_on_profile_screen(),
            'is_followers_list': self.is_followers_list_open(),
            'is_post_grid': self.is_post_grid_visible(),
            'is_story_viewer': self.is_story_viewer_open(),
            'visible_posts': self.count_visible_posts(),
            'visible_stories': self.count_visible_stories(),
            'errors': self.detect_error_messages(),
            'is_rate_limited': self.is_rate_limited(),
            'popup_detected': self.detect_popup_or_modal()
        }

    def is_post_liked(self) -> bool:
        return self._detect_element(self.detection_selectors.liked_button_indicators, "Liked button", log_found=True)

    # === Story detection ===

    def is_story_viewer_open(self) -> bool:
        return self._detect_element(self.detection_selectors.story_viewer_indicators, "Story viewer")
    
    def count_visible_stories(self) -> int:
        try:
            count = 0
            for selector in self.detection_selectors.story_ring_indicators:
                elements = self.device.xpath(selector).all()
                if elements:
                    count = len(elements)
                    break
            
            self.logger.debug(f"{count} visible stories")
            return count
            
        except Exception as e:
            self.logger.debug(f"Error counting stories: {e}")
            return 0
    
    def get_story_count_from_viewer(self) -> tuple[int, int]:
        try:
            from ....ui.selectors import STORY_SELECTORS
            
            element = self.device.xpath(STORY_SELECTORS.story_viewer_text_container).get()
            
            if element:
                content_desc = element.attrib.get('content-desc', '')
                self.logger.debug(f"📱 Story viewer content-desc: {content_desc}")
                
                import re
                pattern = r'story\s+(\d+)\s+of\s+(\d+)'
                match = re.search(pattern, content_desc, re.IGNORECASE)
                
                if match:
                    current_story = int(match.group(1))
                    total_stories = int(match.group(2))
                    self.logger.info(f"📊 Stories detected: {current_story}/{total_stories}")
                    return (current_story, total_stories)
                else:
                    self.logger.debug(f"⚠️ Pattern 'story X of Y' not found in: {content_desc}")
                    return (0, 0)
            else:
                self.logger.debug("⚠️ Element story_viewer_text_container not found")
                return (0, 0)
                
        except Exception as e:
            self.logger.debug(f"Error extracting story count: {e}")
            return (0, 0)
    
    def has_stories(self) -> bool:
        try:
            return self.count_visible_stories() > 0
        except Exception as e:
            self.logger.debug(f"Error checking stories: {e}")
            return False

    # === Post grid detection ===

    def count_visible_posts(self) -> int:
        count = 0
        for selector in self.detection_selectors.post_thumbnail_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    count = len(elements.all())
                    break
            except Exception:
                continue
        
        self.logger.debug(f"{count} visible posts in grid")
        return count
