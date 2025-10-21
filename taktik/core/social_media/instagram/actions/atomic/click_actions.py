"""Atomic click actions for Instagram."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ..core.base_action import BaseAction
from ...ui.selectors import PROFILE_SELECTORS, DETECTION_SELECTORS, BUTTON_SELECTORS, POST_SELECTORS


class ClickActions(BaseAction):
    
    def __init__(self, device):
        super().__init__(device)
        self.logger = logger.bind(module="instagram-click-atomic")
        self.detection_selectors = DETECTION_SELECTORS
        self.selectors = BUTTON_SELECTORS  # Pour les boutons d'interaction
        self.profile_selectors = PROFILE_SELECTORS
        self.post_selectors = POST_SELECTORS
    
    def click_follow_button(self) -> bool:
        self.logger.debug("👤 Clicking Follow button")
        
        if self._find_and_click(self.profile_selectors.follow_button, timeout=5):
            return True
        
        self.logger.warning("Follow button not found")
        return False
    
    def click_unfollow_button(self) -> bool:
        self.logger.debug("👤 Clicking Unfollow button")
        
        if self._find_and_click(self.profile_selectors.following_button, timeout=5):
            return True
        
        self.logger.warning("Unfollow button not found")
        return False
    
    def click_like_button(self) -> bool:
        self.logger.debug("❤️ Clicking Like button")
        
        return self._find_and_click(self.selectors.like_button, timeout=3)
    
    def like_post(self) -> bool:
        return self.click_like_button()
    
    def unlike_post(self) -> bool:
        return self.click_unlike_button()
    
    def click_unlike_button(self) -> bool:
        self.logger.debug("💔 Clicking Unlike button")
        
        if self._find_and_click(self.selectors.like_button, timeout=5):
            return True
        
        self.logger.warning("Unlike button not found")
        return False
    
    def click_comment_button(self) -> bool:
        self.logger.debug("💬 Clicking Comment button")
        
        if self._find_and_click(self.selectors.comment_button, timeout=5):
            return True
        
        self.logger.warning("Comment button not found")
        return False
    
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
        self.logger.debug("📤 Clicking Share button")
        
        if self._find_and_click(self.selectors.share_button, timeout=5):
            return True
        
        self.logger.warning("Share button not found")
        return False
    
    def click_save_button(self) -> bool:
        self.logger.debug("🔖 Clicking Save button")
        
        if self._find_and_click(self.selectors.save_button, timeout=5):
            return True
        
        self.logger.warning("Save button not found")
        return False
    
    def click_story_like_button(self) -> bool:
        self.logger.debug("❤️ Clicking Story Like button")
        
        if self._find_and_click(self.selectors.like_button, timeout=3):
            return True
        
        self.logger.warning("Story Like button not found")
        return False
    
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
        self.logger.debug("👥 Clicking followers count")
        
        if self._find_and_click(self.profile_selectors.followers_count, timeout=5):
            return True
        
        self.logger.warning("Followers count not clickable")
        return False
    
    def click_following_count(self) -> bool:
        self.logger.debug("👥 Clicking following count")
        
        if self._find_and_click(self.profile_selectors.following_count, timeout=5):
            return True
        
        self.logger.warning("Following count not clickable")
        return False
    
    def click_posts_count(self) -> bool:
        self.logger.debug("📸 Clicking posts count")
        
        if self._find_and_click(self.profile_selectors.posts_count, timeout=5):
            return True
        
        self.logger.warning("Posts count not clickable")
        return False
    
    def click_story_ring(self, story_index: int = 0) -> bool:
        self.logger.debug(f"📱 Clicking story #{story_index}")
        
        # Trouver toutes les stories
        story_elements = []
        from ...ui.selectors import STORY_SELECTORS
        for selector in STORY_SELECTORS.story_ring_indicators if hasattr(STORY_SELECTORS, 'story_ring_indicators') else [STORY_SELECTORS.story_ring]:
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
        self.logger.debug("❌ Clicking close button")
        
        from ...ui.selectors import NAVIGATION_SELECTORS
        if self._find_and_click(NAVIGATION_SELECTORS.close_button, timeout=3):
            return True
        
        self.logger.warning("Close button not found")
        return False
    
    def click_back_button(self) -> bool:
        self.logger.debug("⬅️ Clicking back button")
        
        from ...ui.selectors import NAVIGATION_SELECTORS
        if self._find_and_click(NAVIGATION_SELECTORS.back_button, timeout=3):
            return True
        
        self.logger.warning("Back button not found")
        return False
    
    def click_message_button(self) -> bool:
        self.logger.debug("💌 Clicking Message button")
        
        if self._find_and_click(self.profile_selectors.message_button, timeout=5):
            return True
        
        self.logger.warning("Message button not found")
        return False
    
    def is_follow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.follow_button)
    
    def is_unfollow_button_available(self) -> bool:
        return self._is_element_present(self.profile_selectors.following_button)
    
    def is_like_button_available(self) -> bool:
        return self._is_element_present(self.selectors.like_button)
    
    def is_post_already_liked(self) -> bool:
        return self._is_element_present(self.selectors.like_button)
    
    def get_follow_button_state(self) -> str:
        if self.is_follow_button_available():
            return 'follow'
        elif self.is_unfollow_button_available():
            return 'unfollow'
        elif self._is_element_present(self.profile_selectors.message_button):
            return 'message'
        else:
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
