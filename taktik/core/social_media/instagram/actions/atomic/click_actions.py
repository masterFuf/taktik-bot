"""Atomic click actions for Instagram."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import (
    PROFILE_SELECTORS, DETECTION_SELECTORS, BUTTON_SELECTORS, 
    POST_SELECTORS, NAVIGATION_SELECTORS, STORY_SELECTORS
)


class ClickActions(BaseAction):
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-click-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = BUTTON_SELECTORS  # Pour les boutons d'interaction
        self.profile_selectors = PROFILE_SELECTORS
        self.post_selectors = POST_SELECTORS
        self.navigation_selectors = NAVIGATION_SELECTORS
        self.story_selectors = STORY_SELECTORS
    
    def _click_button(self, selectors, button_name: str, emoji: str = "👆", timeout: float = 5) -> bool:
        """
        Generic method to click a button with selectors.
        
        Args:
            selectors: Selector or list of selectors
            button_name: Name for logging
            emoji: Emoji for logging
            timeout: Click timeout
            
        Returns:
            True if clicked, False otherwise
        """
        self.logger.debug(f"{emoji} Clicking {button_name}")
        
        if self._find_and_click(selectors, timeout=timeout):
            return True
        
        self.logger.warning(f"{button_name} not found")
        return False
    
    def click_follow_button(self) -> bool:
        return self._click_button(self.profile_selectors.follow_button, "Follow button", "👤")
    
    def click_unfollow_button(self) -> bool:
        return self._click_button(self.profile_selectors.following_button, "Unfollow button", "👤")
    
    def click_like_button(self) -> bool:
        return self._click_button(self.selectors.like_button, "Like button", "❤️", timeout=3)
    
    def like_post(self) -> bool:
        return self.click_like_button()
    
    def unlike_post(self) -> bool:
        return self.click_unlike_button()
    
    def click_unlike_button(self) -> bool:
        return self._click_button(self.selectors.like_button, "Unlike button", "💔")
    
    def click_comment_button(self) -> bool:
        return self._click_button(self.selectors.comment_button, "Comment button", "💬")
    
    def follow_user(self, username: str) -> bool:
        try:
            self.logger.info(f"👤 Attempting to follow @{username}")
            
            follow_selectors = PROFILE_SELECTORS.advanced_follow_selectors + [
                PROFILE_SELECTORS.follow_button,
                PROFILE_SELECTORS.follow_buttons,
                PROFILE_SELECTORS.suivre_buttons
            ]
            
            if self._find_and_click(follow_selectors, timeout=5):
                # Vérifier qu'on n'a pas navigué vers la liste des followers
                self._human_like_delay('click')
                
                if self._verify_follow_success(username):
                    self.logger.info(f"✅ Successfully followed @{username}")
                    return True
                else:
                    self.logger.warning(f"❌ Clicked but not on the right button for @{username}")
                    return False
            else:
                self.logger.warning(f"❌ Follow button not found for @{username}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Failed to follow @{username}: {e}")
            return False
    
    def _verify_follow_success(self, username: str) -> bool:
        try:
            for indicator in self.detection_selectors.followers_list_indicators:
                if self.device.xpath(indicator).exists:
                    self.logger.warning(f"❌ Navigation to list detected for @{username}")
                    self.device.press("back")
                    return False
            
            # Vérifier qu'on est toujours sur un profil
            from .detection_actions import DetectionActions
            detection = DetectionActions(self.device)
            
            if detection.is_on_profile_screen():
                self.logger.debug(f"✅ Still on profile after follow @{username}")
                return True
            else:
                self.logger.warning(f"❌ Not on profile after follow attempt @{username}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying follow @{username}: {e}")
            return True
    
    def click_share_button(self) -> bool:
        return self._click_button(self.selectors.share_button, "Share button", "📤")
    
    def click_save_button(self) -> bool:
        return self._click_button(self.selectors.save_button, "Save button", "🔖")
    
    def click_story_like_button(self) -> bool:
        return self._click_button(self.selectors.like_button, "Story Like button", "❤️", timeout=3)
    
    def click_post_thumbnail(self, post_index: int = 0) -> bool:
        self.logger.debug(f"🖼️ Clicking post thumbnail #{post_index}")
        
        # Trouver tous les posts
        post_elements = []
        for selector in self.post_selectors.first_post_grid:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    post_elements = elements.all()
                    break
            except Exception:
                continue
        
        if not post_elements:
            self.logger.warning("No post thumbnails found")
            return False
        
        if post_index >= len(post_elements):
            self.logger.warning(f"Index {post_index} out of bounds (max: {len(post_elements)-1})")
            return False
        
        try:
            post_elements[post_index].click()
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.error(f"Error clicking post: {e}")
            return False
    
    def click_followers_count(self) -> bool:
        return self._click_button(self.profile_selectors.followers_count, "Followers count", "👥")
    
    def click_following_count(self) -> bool:
        return self._click_button(self.profile_selectors.following_count, "Following count", "👥")
    
    def click_posts_count(self) -> bool:
        return self._click_button(self.profile_selectors.posts_count, "Posts count", "📸")
    
    def click_story_ring(self, story_index: int = 0) -> bool:
        self.logger.debug(f"📱 Clicking story #{story_index}")
        
        # Trouver toutes les stories
        story_elements = []
        for selector in self.story_selectors.story_ring_indicators if hasattr(self.story_selectors, 'story_ring_indicators') else [self.story_selectors.story_ring]:
            try:
                elements = self.device.xpath(selector)
                if elements.exists:
                    story_elements = elements.all()
                    break
            except Exception:
                continue
        
        if not story_elements:
            self.logger.warning("No stories found")
            return False
        
        if story_index >= len(story_elements):
            self.logger.warning(f"Index {story_index} out of bounds (max: {len(story_elements)-1})")
            return False
        
        try:
            story_elements[story_index].click()
            self._human_like_delay('click')
            return True
        except Exception as e:
            self.logger.error(f"Error clicking story: {e}")
            return False
    
    def click_close_button(self) -> bool:
        return self._click_button(self.navigation_selectors.close_button, "Close button", "❌", timeout=3)
    
    def click_back_button(self) -> bool:
        return self._click_button(self.navigation_selectors.back_button, "Back button", "⬅️", timeout=3)
    
    def click_message_button(self) -> bool:
        return self._click_button(self.profile_selectors.message_button, "Message button", "💌")
    
    def is_follow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.follow_button)
    
    def is_unfollow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.following_button)
    
    def is_like_button_available(self) -> bool:
        return self._is_element_present(self.selectors.like_button)
    
    def is_post_already_liked(self) -> bool:
        return self._is_element_present(self.selectors.like_button)
    
    def get_follow_button_state(self) -> str:
        """
        Detect the follow button state by checking the button text.
        Returns: 'follow', 'following', 'requested', 'message', or 'unknown'
        """
        # Check for "Following" button FIRST (we already follow this user)
        # Must check before "Follow" because resource-id is the same!
        following_selectors = [
            '//android.widget.Button[contains(@text, "Following")]',
            '//android.widget.Button[contains(@text, "Abonné")]',
            '//android.widget.Button[contains(@text, "Suivi")]',
            '//*[@resource-id="com.instagram.android:id/profile_header_follow_button" and contains(@text, "Following")]',
            '//*[@resource-id="com.instagram.android:id/profile_header_follow_button" and contains(@text, "Abonné")]',
        ]
        for selector in following_selectors:
            if self.device.xpath(selector).exists:
                return 'following'
        
        # Check for "Requested" button (pending follow request)
        requested_selectors = [
            '//android.widget.Button[contains(@text, "Requested")]',
            '//android.widget.Button[contains(@text, "Demandé")]',
            '//*[contains(@text, "Requested")]',
        ]
        for selector in requested_selectors:
            if self.device.xpath(selector).exists:
                return 'requested'
        
        # Check for "Follow" button (we don't follow this user)
        follow_selectors = [
            '//android.widget.Button[@text="Follow"]',
            '//android.widget.Button[@text="Suivre"]',
            '//android.widget.Button[contains(@text, "Follow") and not(contains(@text, "Following"))]',
            '//android.widget.Button[contains(@text, "Suivre") and not(contains(@text, "Abonné"))]',
            '//*[@resource-id="com.instagram.android:id/profile_header_follow_button" and @text="Follow"]',
            '//*[@resource-id="com.instagram.android:id/profile_header_follow_button" and @text="Suivre"]',
        ]
        for selector in follow_selectors:
            if self.device.xpath(selector).exists:
                return 'follow'
        
        # Check for Message button (usually means we follow them)
        if self._is_element_present(self.profile_selectors.message_button):
            return 'message'
        
        return 'unknown'

    def click_first_post_in_grid(self) -> bool:
        self.logger.debug("📸 Clicking first post in grid")
        
        try:
            posts = self.device.xpath(self.detection_selectors.post_grid_selector).all()
            
            if not posts:
                self.logger.warning("❌ No posts found in grid with image_button selector")
                return False
            
            self.logger.info(f"✅ Found {len(posts)} posts in grid")
            
            first_post = posts[0]
            if first_post.exists:
                first_post.click()
                self.logger.info("✅ Successfully clicked first post")
                return True
            else:
                self.logger.warning("❌ First post no longer exists")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error clicking first post: {e}")
            return False
    
    def click_recent_posts_tab(self) -> bool:
        try:
            self.logger.debug("📋 Clicking Recent tab")
            
            for selector in self.detection_selectors.recent_tab_selectors:
                if self._find_and_click(selector, timeout=2):
                    self.logger.debug("✅ Successfully clicked Recent tab")
                    return True
            
            self.logger.debug("❌ Cannot find Recent tab")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error clicking Recent tab: {e}")
            return False
    
    def click_post_in_grid(self, post_index: int = 0) -> bool:
        try:
            self.logger.debug(f"📸 Clicking post {post_index} in grid")
            
            for selector in self.detection_selectors.post_grid_selectors:
                try:
                    posts = self.device.xpath(selector).all()
                    if posts and len(posts) > post_index:
                        target_post = posts[post_index]
                        if target_post.exists:
                            target_post.click()
                            self.logger.debug(f"✅ Successfully clicked post {post_index}")
                            return True
                except Exception as ex:
                    self.logger.debug(f"Selector {selector} failed: {ex}")
                    continue
            
            self.logger.warning(f"❌ Cannot click post {post_index}")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error clicking post {post_index}: {e}")
            return False
    
    def click_likes_count(self) -> bool:
        try:
            self.logger.debug("❤️ Clicking likes count")
            
            for selector in self.detection_selectors.likes_count_selectors:
                if self._find_and_click(selector, timeout=2):
                    self.logger.debug("✅ Successfully clicked likes count")
                    return True
            
            self.logger.debug("❌ Cannot find likes count")
            return False
            
        except Exception as e:
            self.logger.error(f"❌ Error clicking likes count: {e}")
            return False
