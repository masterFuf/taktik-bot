"""Post interaction actions (like, unlike, comment, share, save, grid clicks)."""

from typing import Optional, Dict, Any, List
from loguru import logger

from ...core.base_action import BaseAction
from ....ui.selectors import (
    PROFILE_SELECTORS, DETECTION_SELECTORS, BUTTON_SELECTORS,
    POST_SELECTORS, NAVIGATION_SELECTORS
)


class PostInteractionMixin(BaseAction):
    """Mixin: post-level clicks (like/unlike/comment/share/save) and grid navigation."""

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

    # === Post interaction buttons ===

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
    
    def click_share_button(self) -> bool:
        return self._click_button(self.selectors.share_button, "Share button", "📤")
    
    def click_save_button(self) -> bool:
        return self._click_button(self.selectors.save_button, "Save button", "🔖")

    def is_like_button_available(self) -> bool:
        return self._is_element_present(self.selectors.like_button)
    
    def is_post_already_liked(self) -> bool:
        return self._is_element_present(self.selectors.like_button)

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

    # === Grid navigation ===

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

    def click_first_post_in_grid(self) -> bool:
        self.logger.debug("📸 Clicking first post in grid")
        
        try:
            posts = self.device.xpath(self.detection_selectors.post_grid_selector).all()
            
            if not posts:
                self.logger.warning("❌ No posts found in grid with image_button selector")
                return False
            
            self.logger.info(f"✅ Found {len(posts)} posts in grid")
            
            first_post = posts[0]
            first_post.click()
            self.logger.info("✅ Successfully clicked first post")
            return True
                
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

    # === Navigation buttons (used from post context) ===

    def click_close_button(self) -> bool:
        return self._click_button(self.navigation_selectors.close_button, "Close button", "❌", timeout=3)
    
    def click_back_button(self) -> bool:
        return self._click_button(self.navigation_selectors.back_button, "Back button", "⬅️", timeout=3)
