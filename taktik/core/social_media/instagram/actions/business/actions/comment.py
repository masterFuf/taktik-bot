import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ...core.base_business_action import BaseBusinessAction


class CommentBusiness(BaseBusinessAction):
    
    def __init__(self, device, session_manager=None, automation=None):
        super().__init__(device, session_manager, automation, "comment")
        
        from ....ui.selectors import POST_SELECTORS
        self.post_selectors = POST_SELECTORS
        
        self.default_config = {
            'comment_delay_range': (3, 7),
            'max_comment_length': 150,
            'min_comment_length': 3
        }
        
        self.comment_templates = {
            'generic': [
                "Nice! 🔥",
                "Love this! ❤️",
                "Amazing! 😍",
                "Great content! 👏",
                "Awesome! ✨",
                "Beautiful! 💫",
                "Incredible! 🙌",
                "Perfect! 💯",
                "So cool! 😎",
                "Fantastic! ⭐"
            ],
            'engagement': [
                "This is great! 🔥",
                "Love your content! ❤️",
                "Keep it up! 💪",
                "Amazing work! 👏",
                "So inspiring! ✨",
                "This is fire! 🔥",
                "Absolutely love this! 😍",
                "You're killing it! 💯",
                "Can't get enough! 🙌",
                "This made my day! ☀️"
            ],
            'short': [
                "🔥",
                "❤️",
                "😍",
                "👏",
                "✨",
                "💯",
                "🙌",
                "⭐",
                "💪",
                "👌"
            ]
        }
    
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
                    comment_text = self._get_random_comment(template_category)
                    self.logger.debug(f"Using template comment from category: {template_category}")
            
            if not self._validate_comment(comment_text, config):
                self.logger.warning(f"Invalid comment text: {comment_text}")
                stats['errors'] += 1
                return stats
            
            self.logger.info(f"Attempting to comment: '{comment_text}'")
            
            if not self._click_comment_button():
                self.logger.error("Failed to click comment button")
                stats['errors'] += 1
                return stats
            
            self._human_like_delay(1, 2)
            
            if not self._type_comment(comment_text):
                self.logger.error("Failed to type comment")
                stats['errors'] += 1
                return stats
            
            self._human_like_delay(0.5, 1.5)
            
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
                    center_x = (bounds.get('left', 540) + bounds.get('right', 540)) // 2
                    start_y = bounds.get('top', 100)
                    end_y = 1500
                    
                    self.logger.debug(f"Swiping drag handle down: ({center_x}, {start_y}) → ({center_x}, {end_y})")
                    self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.3)
                    time.sleep(0.5)
                    self.logger.debug("Comment popup closed with drag handle")
                    return True
            
            if self.nav_actions.close_modal_or_popup():
                self.logger.debug("Comment popup closed with close button")
                return True
            
            self.logger.debug("Fallback: using device back key")
            self.device.press("back")
            time.sleep(0.5)
            return True
            
        except Exception as e:
            self.logger.error(f"Error closing comment popup: {e}")
            return False
    
    def _get_random_comment(self, category: str = 'generic') -> str:
        if category not in self.comment_templates:
            category = 'generic'
        
        templates = self.comment_templates[category]
        return random.choice(templates)
    
    def _validate_comment(self, comment_text: str, config: dict) -> bool:
        if not comment_text or not isinstance(comment_text, str):
            return False
        
        comment_text = comment_text.strip()
        
        if len(comment_text) < config['min_comment_length']:
            self.logger.warning(f"Comment too short: {len(comment_text)} < {config['min_comment_length']}")
            return False
        
        if len(comment_text) > config['max_comment_length']:
            self.logger.warning(f"Comment too long: {len(comment_text)} > {config['max_comment_length']}")
            return False
        
        return True
    
    def get_comment_templates(self, category: str = None) -> List[str]:
        if category and category in self.comment_templates:
            return self.comment_templates[category].copy()
        return self.comment_templates.copy()
    
    def add_custom_template(self, comment: str, category: str = 'generic') -> bool:
        try:
            if category not in self.comment_templates:
                self.comment_templates[category] = []
            
            if comment not in self.comment_templates[category]:
                self.comment_templates[category].append(comment)
                self.logger.debug(f"Custom template added to '{category}': {comment}")
                return True
            
            return False
            
        except Exception as e:
            self.logger.error(f"Error adding custom template: {e}")
            return False
