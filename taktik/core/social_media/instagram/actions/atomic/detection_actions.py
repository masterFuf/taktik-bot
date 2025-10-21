from typing import Optional, Dict, Any, List, Tuple
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import DETECTION_SELECTORS, PROFILE_SELECTORS, POST_SELECTORS


class DetectionActions(BaseAction):
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-detection-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = PROFILE_SELECTORS
        self.post_selectors = POST_SELECTORS
    
    def is_private_account(self) -> bool:
        self.logger.debug("Detecting private account")
        
        if self._is_element_present(self.selectors.private_indicators):
            self.logger.debug("✅ Private account detected via text indicators")
            return True
        
        private_message_selectors = [
            '//*[contains(@text, "This Account is Private")]',
            '//*[contains(@text, "Ce compte est privé")]',
            '//*[contains(@content-desc, "This Account is Private")]',
            '//*[contains(@content-desc, "Ce compte est privé")]'
        ]
        if self._is_element_present(private_message_selectors):
            self.logger.debug("✅ Private account detected via 'Account is Private' message")
            return True
        
        try:
            post_count_selectors = [
                '//*[@resource-id="com.instagram.android:id/row_profile_header_textview_post_count"]',
                '//*[contains(@resource-id, "post_count")]'
            ]
            
            post_count = None
            for selector in post_count_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    text = element.get_text().strip()
                    if text and text.isdigit():
                        post_count = int(text)
                        break
            
            visible_posts = self.count_visible_posts()
            
            if post_count == 0 and visible_posts > 0:
                self.logger.debug(f"✅ Private account detected: post_count=0 but {visible_posts} visible posts in grid")
                return True
            
            if visible_posts > 0:
                clickable_posts = self.device.xpath('//*[@resource-id="com.instagram.android:id/image_button"]').all()
                if not clickable_posts:
                    self.logger.debug(f"✅ Private account detected: {visible_posts} visible posts but none clickable")
                    return True
                    
        except Exception as e:
            self.logger.debug(f"Error in advanced private detection: {e}")
        
        return False
    
    def is_verified_account(self) -> bool:
        self.logger.debug("Detecting verified account")
        verified_selectors = [
            '//*[contains(@content-desc, "Verified")]',
            '//*[contains(@content-desc, "Vérifié")]',
            '//*[@resource-id="com.instagram.android:id/verified_badge"]'
        ]
        return self._is_element_present(verified_selectors)
    
    def is_business_account(self) -> bool:
        self.logger.debug("Detecting business account")
        business_selectors = [
            '//*[contains(@resource-id, "profile_header_business_category")]',
            '//*[contains(@text, "Professional")]',
            '//*[contains(@text, "Professionnel")]'
        ]
        return self._is_element_present(business_selectors)
    
    def get_username_from_profile(self) -> Optional[str]:
        try:
            username_element = self.device.xpath(
                '//*[@resource-id="com.instagram.android:id/action_bar_large_title_auto_size"]'
            )
            
            if username_element.exists:
                username = username_element.get_text().strip()
                if username:
                    self.logger.debug(f"Username found: {username}")
                    return username
            
            app_id = 'com.instagram.android'
            username_selectors = [
                f'//android.widget.TextView[contains(@resource-id, "{app_id}:id/action_bar_title")]',
                f'//android.widget.TextView[contains(@resource-id, "{app_id}:id/action_bar_large_title_auto_size")]',
                f'//android.widget.TextView[contains(@resource-id, "{app_id}:id/row_profile_header_username")]',
                '//android.widget.TextView[contains(@text, "@")]',
            ]
            
            for selector in username_selectors:
                element = self.device.xpath(selector)
                if element.exists:
                    username = element.get_text().strip()
                    if username:
                        username = username.replace('@', '')
                        self.logger.debug(f"Username found with alternative selector: {username}")
                        return username
            
            username_element = self.device.xpath(
                '//*[contains(@content-desc, "@")]'
            )
            if username_element.exists:
                username = username_element.get_attribute('content-desc', '').strip()
                if username and '@' in username:
                    username = username.split('@')[-1].split(' ')[0]
                    self.logger.debug(f"Username extracted from content-desc: {username}")
                    return username
            
            self.logger.warning("Cannot find username from profile")
            return None
            
        except Exception as e:
            self.logger.error(f"Error retrieving username: {e}")
            return None
    
    def get_full_name_from_profile(self) -> Optional[str]:
        full_name_selectors = [
            '//*[@resource-id="com.instagram.android:id/profile_header_full_name"]',
            '//*[contains(@resource-id, "full_name")]'
        ]
        return self._get_text_from_element(full_name_selectors)
    
    def get_biography_from_profile(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.bio)
    
    def get_followers_count_text(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.followers_count)
    
    def get_following_count_text(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.following_count)
    
    def get_posts_count_text(self) -> Optional[str]:
        return self._get_text_from_element(self.selectors.posts_count)
    
    def get_followers_count(self) -> Optional[int]:
        text = self.get_followers_count_text()
        if text:
            return self._extract_number_from_text(text)
        return None
    
    def get_following_count(self) -> Optional[int]:
        text = self.get_following_count_text()
        if text:
            return self._extract_number_from_text(text)
        return None
    
    def get_posts_count(self) -> Optional[int]:
        text = self.get_posts_count_text()
        if text:
            return self._extract_number_from_text(text)
        return None
    
    def is_on_home_screen(self) -> bool:
        return self._is_element_present(self.detection_selectors.home_screen_indicators)
    
    def is_on_search_screen(self) -> bool:
        return self._is_element_present(self.detection_selectors.search_screen_indicators)
    
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
    
    def is_followers_list_open(self) -> bool:
        follow_list_selectors = [
            '//*[@resource-id="com.instagram.android:id/follow_list_container"]',
            '//*[contains(@resource-id, "follow_list")]',
            '//*[contains(@content-desc, "followers") or contains(@content-desc, "following")]'
        ]
        return self._is_element_present(follow_list_selectors)
    
    def is_following_list_open(self) -> bool:
        return self.is_followers_list_open()
    
    def is_post_grid_visible(self) -> bool:
        post_grid_selectors = [
            '//*[@resource-id="com.instagram.android:id/profile_tab_layout"]',
            '//*[contains(@resource-id, "recycler_view")]'
        ]
        return self._is_element_present(post_grid_selectors)
    
    def is_story_viewer_open(self) -> bool:
        return self._is_element_present(self.detection_selectors.story_viewer_indicators)
    
    def count_visible_posts(self) -> int:
        count = 0
        post_thumbnail_selectors = [
            '//*[@resource-id="com.instagram.android:id/image_button"]',
            '//android.widget.ImageView[contains(@resource-id, "image")]'
        ]
        for selector in post_thumbnail_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    count = len(elements.all())
                    break
            except Exception:
                continue
        
        self.logger.debug(f"{count} visible posts in grid")
        return count
    
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
            from ...ui.selectors import STORY_SELECTORS
            
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

    def extract_usernames_from_follow_list(self) -> List[str]:
        usernames = []
        
        follow_list_username_selectors = [
            '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
            '//*[contains(@resource-id, "username")]'
        ]
        for selector in follow_list_username_selectors:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    for element in elements.all():
                        username_text = element.text
                        if username_text:
                            clean_username = self._clean_username(username_text)
                            if self._is_valid_username(clean_username):
                                usernames.append(clean_username)
                    break
            except Exception as e:
                self.logger.debug(f"Error extracting usernames: {e}")
                continue
        
        unique_usernames = list(dict.fromkeys(usernames))
        self.logger.debug(f"{len(unique_usernames)} usernames extracted from list")
        return unique_usernames
    
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
        is_limited = self._is_element_present(self.detection_selectors.rate_limit_indicators)
        if is_limited:
            self.logger.warning("Rate limit detected")
        
        return is_limited
    
    def is_login_required(self) -> bool:
        return self._is_element_present(self.detection_selectors.login_required_indicators)
    
    def detect_popup_or_modal(self) -> Optional[str]:
        for popup_type, selector in self.detection_selectors.popup_types.items():
            if self._is_element_present([selector]):
                self.logger.debug(f"Popup detected: {popup_type}")
                return popup_type
        
        return None
    
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
        self.logger.debug("❤️ Checking if post is already liked")
        return self._is_element_present(self.detection_selectors.liked_button_indicators)
    
    def is_on_post_screen(self) -> bool:
        self.logger.debug("📱 Checking if on post screen")
        return self._is_element_present(self.detection_selectors.post_screen_indicators)
