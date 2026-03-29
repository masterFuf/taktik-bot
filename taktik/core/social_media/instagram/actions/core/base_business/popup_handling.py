"""Popup handling — likers popup, comments view, close popup, follow suggestions."""

import time


class PopupHandlingMixin:
    """Mixin: gestion popups (likers, comments, follow suggestions, close par swipe)."""

    def _is_likers_popup_open(self) -> bool:
        # Fast path: single combined XPath query for likers popup (1 round-trip)
        try:
            combined = ' | '.join(self.popup_selectors.likers_popup_indicators)
            if self.device.xpath(combined).exists:
                # Quick negative check: make sure it's not actually comments view
                comments_combined = ' | '.join(self.popup_selectors.comments_view_indicators[:3])
                if self.device.xpath(comments_combined).exists:
                    self.logger.debug("⚠️ Comments view detected, not likers popup")
                    return False
                return True
        except Exception:
            # Fallback to sequential check if combined XPath fails
            for indicator in self.popup_selectors.likers_popup_indicators:
                if self._is_element_present([indicator]):
                    return True
        return False
    
    def _is_comments_view_open(self) -> bool:
        """Check if we're in the comments view instead of likers popup."""
        try:
            combined = ' | '.join(self.popup_selectors.comments_view_indicators)
            return self.device.xpath(combined).exists
        except Exception:
            for indicator in self.popup_selectors.comments_view_indicators:
                if self._is_element_present([indicator]):
                    return True
            return False
    
    def _close_likers_popup(self):
        try:
            for _ in range(5):
                if not self._is_likers_popup_open():
                    break
                self._close_popup_by_swipe_down()
                time.sleep(1.2)
            self._human_like_delay('popup_close')
        except:
            pass
    
    def _close_popup_by_swipe_down(self) -> bool:
        try:
            handle_element = self.device.xpath(self.popup_selectors.drag_handle_selector)
            
            if handle_element.exists:
                bounds = handle_element.info.get('bounds', {})
                if bounds:
                    handle_y = (bounds.get('top', 710) + bounds.get('bottom', 710)) // 2
                    center_x = (bounds.get('left', 492) + bounds.get('right', 588)) // 2
                    
                    screen_height = self.device.info.get('displayHeight', 1920)
                    
                    # If handle is near top of screen (< 10%), bottom sheet is fully
                    # expanded — swipe won't work, use back press directly
                    if handle_y < int(screen_height * 0.10):
                        self.logger.debug(f"📍 Bottom sheet fully expanded (handle_y={handle_y}), using press('back')")
                        self.device.press("back")
                        time.sleep(0.8)
                        return True
                    
                    self.logger.debug(f"📍 Handle detected at Y={handle_y}, X={center_x}")
                    
                    end_y = int(screen_height * 0.95)
                    
                    self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, duration=0.3)
                    self.logger.debug(f"✅ Swipe to close: ({center_x}, {handle_y}) → ({center_x}, {end_y})")
                    time.sleep(0.5)
                    
                    # Verify — if popup is still open, fallback to back press
                    if self._is_likers_popup_open() or self._is_comments_view_open():
                        self.logger.debug("⚠️ Swipe did not close popup, falling back to press('back')")
                        self.device.press("back")
                        time.sleep(0.8)
                    return True
            
            screen_info = self.device.info
            center_x = screen_info.get('displayWidth', 1080) // 2
            handle_y = int(screen_info.get('displayHeight', 1920) * 0.37)
            end_y = int(screen_info.get('displayHeight', 1920) * 0.95)
            self.device.swipe_coordinates(center_x, handle_y, center_x, end_y, duration=0.3)
            time.sleep(0.5)
            
            # Verify fallback swipe
            if self._is_likers_popup_open() or self._is_comments_view_open():
                self.logger.debug("⚠️ Fallback swipe did not close popup, using press('back')")
                self.device.press("back")
                time.sleep(0.8)
            return True
        except Exception as e:
            self.logger.debug(f"❌ Error closing popup: {e}")
            try:
                self.device.press("back")
                time.sleep(0.5)
            except Exception:
                pass
            return False

    def _handle_follow_suggestions_popup(self):
        try:
            self.logger.debug("🔍 Checking for suggestions popup after follow...")
            
            popup_detected = False
            for selector in self.popup_selectors.follow_suggestions_indicators:
                if self.device.xpath(selector).exists:
                    popup_detected = True
                    self.logger.debug(f"✅ Suggestions popup detected: {selector}")
                    break
            
            if popup_detected:
                # Swipe UP to scroll back to top of profile where posts are visible
                from ..device.facade import Direction
                self.logger.debug("📜 Scrolling up to hide suggestions section...")
                self.device.swipe(Direction.DOWN, scale=0.5)  # DOWN = finger moves down = content goes UP
                time.sleep(0.3)
                self.device.swipe(Direction.DOWN, scale=0.5)  # Second swipe to ensure we're at top
                time.sleep(0.3)
                self.logger.debug("✅ Suggestions section hidden by scrolling up")
            else:
                self.logger.debug("ℹ️ No suggestions popup detected")
                
        except Exception as e:
            self.logger.debug(f"Error handling suggestions popup: {e}")
