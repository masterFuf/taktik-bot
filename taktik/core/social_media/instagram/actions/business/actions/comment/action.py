"""Comment action — post comments on Instagram posts."""

import time
import random
from typing import Dict, List, Any, Optional
from loguru import logger

from ....core.base_business import BaseBusinessAction
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
            # Try primary selector first
            comment_field = self.device.xpath(self.post_selectors.comment_field_selector)

            # Fallback: iterate TEXT_INPUT_SELECTORS.comment_field_selectors
            if not comment_field.exists:
                self.logger.debug("Primary comment field selector missed, trying fallbacks...")
                from .....ui.selectors import TEXT_INPUT_SELECTORS
                for fallback in TEXT_INPUT_SELECTORS.comment_field_selectors:
                    comment_field = self.device.xpath(fallback)
                    if comment_field.exists:
                        self.logger.debug(f"Comment field found with fallback: {fallback}")
                        break

            if not comment_field.exists:
                self.logger.error("Comment field not found (all selectors failed)")
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
            # Try each selector, with a retry after a short wait
            for attempt in range(2):
                for selector in self.post_selectors.post_comment_button_selectors:
                    try:
                        element = self.device.xpath(selector)
                        if element.exists:
                            element.click()
                            self.logger.debug(f"Post comment button clicked with selector: {selector}")
                            time.sleep(1)
                            return True
                    except Exception:
                        continue
                
                if attempt == 0:
                    self.logger.debug("Post comment button not found, waiting 2s and retrying...")
                    time.sleep(2)
            
            self.logger.error("Post comment button not found after retries")
            return False
            
        except Exception as e:
            self.logger.error(f"Error posting comment: {e}")
            return False
    
    def _close_comment_popup(self) -> bool:
        """Close the comments bottom sheet using multiple strategies.

        Root cause (confirmed from UI dump): after posting a comment the
        edittext field stays focused=true. The Taktik IME occupies a separate
        window below the sheet. In this state KEYCODE_BACK is consumed by the
        focused field — it only removes focus / hides the keyboard, not the sheet.

        Strategy order:
        1. Click the sheet title 'Comments' to remove focus from the edittext
           (defocus → IME hides → back now targets the sheet)
        2. press('back') up to 3x with per-attempt verification
        3. Swipe drag handle down (only when sheet is NOT full-screen)
        4. Swipe from screen centre (generic last resort)
        5. Click nav-bar Back button of the IME window (last resort)
        """
        try:
            self.logger.debug("Closing comment popup...")

            screen_info = self.device.info
            screen_height = screen_info.get('displayHeight', 1920)
            screen_width = screen_info.get('displayWidth', 1080)

            # ── Strategy 1: defocus the comment edittext ──────────────────────
            # Click the "Comments" title or the drag handle frame to remove focus
            # from the edittext so that subsequent KEYCODE_BACK targets the sheet.
            try:
                title = self.device.xpath(
                    '//*[@resource-id="com.instagram.android:id/title_text_view"]'
                    '[@text="Comments" or @text="Commentaires"]'
                )
                if title.exists:
                    title.click()
                    self.logger.debug("Clicked Comments title to defocus edittext")
                    time.sleep(0.5)
                    if not self._is_comments_view_open():
                        self.logger.debug("✅ Comment popup closed by title click")
                        return True
                else:
                    # Fallback defocus: click drag handle frame area (safe tap zone)
                    drag_frame = self.device.xpath(
                        '//*[@resource-id="com.instagram.android:id/bottom_sheet_drag_handle_frame"]'
                    )
                    if drag_frame.exists:
                        drag_frame.click()
                        self.logger.debug("Clicked drag handle frame to defocus edittext")
                        time.sleep(0.5)
            except Exception as e:
                self.logger.debug(f"Defocus strategy failed (non-fatal): {e}")

            # ── Strategy 2: press('back') up to 3x with verification ─────────
            # After defocus the IME should be hidden and back targets the sheet.
            for attempt in range(3):
                self.logger.debug(f"press('back') attempt {attempt + 1}/3")
                self.device.press("back")
                time.sleep(0.9)
                if not self._is_comments_view_open():
                    self.logger.debug(f"✅ Comment popup closed after {attempt + 1} back press(es)")
                    return True

            # ── Strategy 3: swipe drag handle down (partial sheet only) ──────
            handle_is_fullscreen = False
            try:
                drag_handle = self.device.xpath(self.popup_selectors.comment_popup_drag_handle)
                if drag_handle.exists:
                    bounds = drag_handle.info.get('bounds', {})
                    if bounds:
                        handle_y = (bounds.get('top', 0) + bounds.get('bottom', 0)) // 2
                        center_x = (bounds.get('left', screen_width // 2) + bounds.get('right', screen_width // 2)) // 2
                        if handle_y < int(screen_height * 0.10):
                            handle_is_fullscreen = True
                            self.logger.debug(f"Sheet fully expanded (handle_y={handle_y}) — skipping swipe")
                        else:
                            end_y = int(screen_height * 0.95)
                            self.logger.debug(f"Swiping drag handle: ({center_x},{handle_y}) → ({center_x},{end_y})")
                            self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, 0.3)
                            time.sleep(0.7)
                            if not self._is_comments_view_open():
                                self.logger.debug("✅ Comment popup closed via drag handle swipe")
                                return True
                            self.logger.debug("Drag handle swipe did not close popup")
            except Exception as e:
                self.logger.debug(f"Drag handle strategy failed (non-fatal): {e}")

            # ── Strategy 4: swipe from screen centre ─────────────────────────
            # Works whether the sheet is partial OR full-screen:
            # swiping from the middle of the modal content area downward
            # dismisses the bottom sheet without risking the notification panel.
            center_x = screen_width // 2
            start_y = int(screen_height * 0.40)
            end_y = int(screen_height * 0.92)
            self.logger.debug(f"Centre swipe: ({center_x},{start_y}) → ({center_x},{end_y})")
            self.device.swipe_coordinates(center_x, start_y, center_x, end_y, 0.4)
            time.sleep(0.7)
            if not self._is_comments_view_open():
                self.logger.debug("✅ Comment popup closed via centre swipe")
                return True

            # ── Strategy 5: click IME nav-bar Back button ─────────────────────
            # The Taktik IME exposes android:id/input_method_nav_back which is
            # clickable — tapping it sends a back event through the IME layer.
            try:
                ime_back = self.device.xpath('//*[@resource-id="android:id/input_method_nav_back"]')
                if ime_back.exists:
                    ime_back.click()
                    self.logger.debug("Clicked IME nav back button")
                    time.sleep(0.7)
                    if not self._is_comments_view_open():
                        self.logger.debug("✅ Comment popup closed via IME back button")
                        return True
                    # One more back press after IME dismissed
                    self.device.press("back")
                    time.sleep(0.8)
                    if not self._is_comments_view_open():
                        self.logger.debug("✅ Comment popup closed after IME back + back press")
                        return True
            except Exception as e:
                self.logger.debug(f"IME back button strategy failed (non-fatal): {e}")

            self.logger.warning("⚠️ All strategies exhausted — could not confirm comment popup closed")
            return True

        except Exception as e:
            self.logger.error(f"Error closing comment popup: {e}")
            try:
                self.device.press("back")
                time.sleep(0.5)
            except Exception:
                pass
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
