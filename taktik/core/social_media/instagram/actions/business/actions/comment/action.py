"""Comment action — post comments on Instagram posts."""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business_action import BaseBusinessAction
from .templates import DEFAULT_TEMPLATES, get_random_comment, validate_comment, get_templates, add_custom_template


class CommentAction(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "comment")
        
        from .....ui.selectors import POST_SELECTORS
        self.post_selectors = POST_SELECTORS
        
        self.default_config = {
            'comment_delay_range': (3, 7),
            'max_comment_length': 150,
            'min_comment_length': 3
        }
        
        # Mutable copy so add_custom_template works at runtime
        self.comment_templates = {k: list(v) for k, v in DEFAULT_TEMPLATES.items()}
    
    def comment_on_post(self, comment_text: str = None, template_category: str = 'generic',
                       custom_comments: List[str] = None, config: dict = None, username: str = None) -> dict:
        config = {**self.default_config, **(config or {})}
        
        stats = {
            'commented': False,
            'comment_text': None,
            'errors': 0,
            'success': False
        }
        
        try:
            if not comment_text:
                if custom_comments and len(custom_comments) > 0:
                    comment_text = random.choice(custom_comments)
                    self.logger.debug(f"Using custom comment from user list")
                else:
                    comment_text = get_random_comment(self.comment_templates, template_category)
                    self.logger.debug(f"Using template comment from category: {template_category}")
            
            if not validate_comment(comment_text, config, self.logger):
                self.logger.warning(f"Invalid comment text: {comment_text}")
                stats['errors'] += 1
                return stats
            
            self.logger.info(f"Attempting to comment: '{comment_text}'")
            
            if not self._click_comment_button():
                self.logger.error("Failed to click comment button")
                stats['errors'] += 1
                return stats
            
            time.sleep(random.uniform(1, 2))
            
            if not self._type_comment(comment_text):
                self.logger.error("Failed to type comment")
                stats['errors'] += 1
                return stats
            
            time.sleep(random.uniform(0.5, 1.5))
            
            if not self._post_comment():
                self.logger.error("Failed to post comment")
                stats['errors'] += 1
                return stats
            
            self.logger.info(f"✅ Comment posted successfully: '{comment_text}'")
            stats['commented'] = True
            stats['comment_text'] = comment_text
            stats['success'] = True
            
            delay = random.uniform(*config['comment_delay_range'])
            self.logger.debug(f"Waiting {delay:.1f}s after commenting")
            time.sleep(delay)
            
            self._close_comment_popup()
            
            # Record quota
            try:
                if self.session_manager:
                    self.session_manager.record_action('comment', success=True)
                    self.logger.debug("Comment quota incremented")
            except Exception as e:
                self.logger.error(f"Failed to increment comment quota: {e}")
                stats['errors'] += 1
            
            # Record comment in database
            if username:
                self._record_action(username, 'COMMENT', 1)
            
            return stats
            
        except Exception as e:
            self.logger.error(f"Error commenting on post: {e}")
            stats['errors'] += 1
            return stats
    
    def _click_comment_button(self) -> bool:
        try:
            for selector in self.post_selectors.comment_button_selectors:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        self.logger.debug(f"Comment button clicked with selector: {selector}")
                        return True
                except Exception as e:
                    self.logger.debug(f"Failed with selector {selector}: {e}")
                    continue
            
            self.logger.warning("Comment button not found")
            return False
            
        except Exception as e:
            self.logger.error(f"Error clicking comment button: {e}")
            return False
    
    def _type_comment(self, comment_text: str) -> bool:
        try:
            comment_field = self.device.xpath(self.post_selectors.comment_field_selector)
            
            if not comment_field.exists:
                self.logger.error("Comment field not found")
                return False
            
            comment_field.click()
            time.sleep(0.5)
            
            # Use Taktik Keyboard for reliable text input
            if not self._type_with_taktik_keyboard(comment_text):
                self.logger.warning("Taktik Keyboard failed, falling back to set_text")
                comment_field.set_text(comment_text)
            self.logger.debug(f"Comment text typed: '{comment_text}'")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error typing comment: {e}")
            return False
    
    def _post_comment(self) -> bool:
        try:
            post_button = self.device.xpath(self.post_selectors.post_comment_button_selector)
            
            if not post_button.exists:
                self.logger.error("Post comment button not found")
                return False
            
            post_button.click()
            self.logger.debug("Post comment button clicked")
            
            time.sleep(1)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error posting comment: {e}")
            return False
    
    def _close_comment_popup(self) -> bool:
        try:
            self.logger.debug("Closing comment popup...")
            
            drag_handle = self.device.xpath(self.popup_selectors.comment_popup_drag_handle)
            
            if drag_handle.exists:
                bounds = drag_handle.info.get('bounds', {})
                if bounds:
                    screen_info = self.device.info
                    screen_height = screen_info.get('displayHeight', 1920)
                    screen_width = screen_info.get('displayWidth', 1080)
                    
                    handle_y = (bounds.get('top', 100) + bounds.get('bottom', 100)) // 2
                    center_x = (bounds.get('left', screen_width // 2) + bounds.get('right', screen_width // 2)) // 2
                    
                    # If handle is near status bar (< 5% of screen), use a safe start position
                    if handle_y < int(screen_height * 0.05):
                        handle_y = int(screen_height * 0.05)
                        self.logger.debug(f"Handle too close to status bar, adjusting start_y to {handle_y}")
                    
                    end_y = int(screen_height * 0.95)
                    
                    self.logger.debug(f"Swiping drag handle down: ({center_x}, {handle_y}) → ({center_x}, {end_y})")
                    self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, 0.3)
                    time.sleep(0.5)
                    self.logger.debug("Comment popup closed with drag handle")
                    return True
            
            # Fallback: swipe from center of screen like _close_popup_by_swipe_down
            screen_info = self.device.info
            center_x = screen_info.get('displayWidth', 1080) // 2
            handle_y = int(screen_info.get('displayHeight', 1920) * 0.37)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.95)
            self.logger.debug(f"Fallback swipe: ({center_x}, {handle_y}) → ({center_x}, {end_y})")
            self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, 0.3)
            time.sleep(0.5)
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing comment popup: {e}")
            return False
    
    # ─── Backward-compatible template management methods ─────────────────
    
    def _get_random_comment(self, category: str = 'generic') -> str:
        return get_random_comment(self.comment_templates, category)
    
    def _validate_comment(self, comment_text: str, config: dict) -> bool:
        return validate_comment(comment_text, config, self.logger)
    
    def get_comment_templates(self, category: str = None) -> object:
        return get_templates(self.comment_templates, category)
    
    def add_custom_template(self, comment: str, category: str = 'generic') -> bool:
        return add_custom_template(self.comment_templates, comment, category, self.logger)
