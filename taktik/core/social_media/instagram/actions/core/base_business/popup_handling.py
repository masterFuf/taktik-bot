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
    
    def _find_like_count_element(self):
        """Find the like count element on the current post (reel-aware)."""
        return self.ui_extractors.find_like_count_element(logger_instance=self.logger)

    def _open_comments_view(self) -> bool:
        """Open the comments thread of the current post.

        Canonical production flow (workflows + Cartography Lab), the counterpart of
        `_open_likers_popup`: tap the post's comment button, then confirm the thread is
        actually showing. A post with no comments at all is closed again and reported as
        not opened — there is nobody to engage there.
        """
        from taktik.core.social_media.instagram.ui.selectors.surfaces.post import (
            POST_COMMENTS_SELECTORS,
        )

        try:
            opened = False
            for selector in self.button_selectors.comment_button:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    time.sleep(2)
                    opened = True
                    break

            if not opened:
                self.logger.warning("⚠️ No comment button found on this post")
                return False

            if self.device.xpath(POST_COMMENTS_SELECTORS.comment_empty_state_view).exists:
                self.logger.info("Post has no comments — nothing to engage with here")
                self.device.press("back")
                time.sleep(0.5)
                return False

            if not self._is_comments_view_open():
                self.logger.warning("⚠️ Comment button tapped but the thread did not open")
                return False

            self.logger.info("💬 Comments thread opened")
            return True
        except Exception as exc:
            self.logger.error(f"Error opening comments view: {exc}")
            return False

    def _open_likers_popup(self, is_reel: bool = False) -> bool:
        """Open the likers popup of the current post.

        Canonical production flow (shared by workflows and the Cartography Lab):
        find the like-count element (reel-aware), click it, abort if it opened
        the comments view by mistake, and confirm the likers popup is open.
        """
        try:
            like_count_element = self._find_like_count_element()

            if not like_count_element:
                self.logger.warning("⚠️ No like counter found - post may not have visible like count")
                return False

            like_count_element.click()
            self._human_like_delay('click')
            time.sleep(1.5)

            # Check if we accidentally opened comments instead of likers
            if self._is_comments_view_open():
                self.logger.warning("⚠️ Opened comments view instead of likers popup - closing and aborting")
                self._close_comments_view()
                return False

            if self._is_likers_popup_open():
                post_type = "reel" if is_reel else "post"
                self.logger.info(f"✅ Likers popup opened ({post_type})")
                return True

            self.logger.error("❌ Could not open likers popup")
            return False

        except Exception as e:
            self.logger.error(f"Error opening likers popup: {e}")
            return False

    def _close_comments_view(self) -> bool:
        """Close comments view if accidentally opened."""
        try:
            for selector in self.navigation_selectors.back_buttons[:3]:
                try:
                    element = self.device.xpath(selector)
                    if element.exists:
                        element.click()
                        time.sleep(0.5)
                        if not self._is_comments_view_open():
                            self.logger.debug("✅ Comments view closed")
                            return True
                except Exception:
                    continue

            self.device.press('back')
            time.sleep(0.5)
            return not self._is_comments_view_open()
        except Exception as e:
            self.logger.debug(f"Error closing comments view: {e}")
            return False

    def _close_likers_popup(self):
        try:
            for _ in range(5):
                if not self._is_likers_popup_open():
                    break
                self._close_popup_by_swipe_down()
                time.sleep(1.2)
            self._human_like_delay('popup_close')
        except Exception:
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

    def _handle_follow_suggestions_popup(self) -> bool:
        """Observe Instagram's inline post-follow suggestions without moving the profile.

        The suggestions are not a blocking modal. Scrolling them away used to pull the profile
        toward refresh immediately after a successful follow, so the production handler now only
        records their presence and lets normal back-navigation leave the profile.
        """
        try:
            self.logger.debug("🔍 Checking for inline suggestions after follow...")
            
            for selector in self.popup_selectors.follow_suggestions_indicators:
                if self.device.xpath(selector).exists:
                    self.logger.debug(
                        f"✅ Inline suggestions detected and left in place: {selector}"
                    )
                    return True

            self.logger.debug("ℹ️ No inline suggestions detected")
            return False
                
        except Exception as e:
            self.logger.debug(f"Error observing inline suggestions: {e}")
            return False

    def _is_ad_consent_popup_open(self) -> bool:
        """Check if the Meta ad consent popup (page 1 or 2) is visible."""
        try:
            for indicator in self.popup_selectors.ad_consent_page1_indicators:
                if self._is_element_present([indicator]):
                    return True
            for indicator in self.popup_selectors.ad_consent_page2_indicators:
                if self._is_element_present([indicator]):
                    return True
        except Exception:
            pass
        return False

    def _handle_ad_consent_popup(self) -> bool:
        """Handle the Meta ad consent popup (2-page flow).
        
        Page 1: Select "Use free of charge with ads" → Click "Continue"
        Page 2: Click "Agree"
        
        Returns True if the popup was detected and handled.
        """
        try:
            # --- Page 1 detection ---
            page1_detected = False
            for indicator in self.popup_selectors.ad_consent_page1_indicators:
                if self._is_element_present([indicator]):
                    page1_detected = True
                    break
            
            if page1_detected:
                self.logger.info("🪟 Meta ad consent popup detected (page 1)")
                
                # Click "Use free of charge with ads" radio option
                if self._find_and_click(self.popup_selectors.ad_consent_free_option, timeout=3):
                    self.logger.debug("✅ Selected 'Use free of charge with ads'")
                    time.sleep(1)
                else:
                    self.logger.warning("⚠️ Could not find free option, trying Continue directly")
                
                # Click "Continue"
                if self._find_and_click(self.popup_selectors.ad_consent_continue_button, timeout=5):
                    self.logger.debug("✅ Clicked Continue")
                    time.sleep(2)
                else:
                    self.logger.warning("⚠️ Could not click Continue on ad consent page 1")
                    return False
            
            # --- Page 2 detection ---
            page2_detected = False
            for indicator in self.popup_selectors.ad_consent_page2_indicators:
                if self._is_element_present([indicator]):
                    page2_detected = True
                    break
            
            # Also check if we just navigated from page 1
            if not page2_detected and page1_detected:
                # Wait a bit and re-check after clicking Continue
                time.sleep(1)
                for indicator in self.popup_selectors.ad_consent_page2_indicators:
                    if self._is_element_present([indicator]):
                        page2_detected = True
                        break
            
            if page2_detected:
                self.logger.info("🪟 Meta ad consent popup detected (page 2)")
                
                # Click "Agree"
                if self._find_and_click(self.popup_selectors.ad_consent_agree_button, timeout=5):
                    self.logger.info("✅ Ad consent popup dismissed (clicked Agree)")
                    time.sleep(1.5)
                    return True
                else:
                    self.logger.warning("⚠️ Could not click Agree on ad consent page 2")
                    return False
            
            if page1_detected:
                # Page 1 was handled but page 2 didn't appear
                return True
            
            # --- Page 3: "You can manage your ad experience" → Click OK ---
            page3_detected = False
            for indicator in self.popup_selectors.ad_consent_page3_indicators:
                if self._is_element_present([indicator]):
                    page3_detected = True
                    break
            
            if not page3_detected and (page1_detected or page2_detected):
                time.sleep(1)
                for indicator in self.popup_selectors.ad_consent_page3_indicators:
                    if self._is_element_present([indicator]):
                        page3_detected = True
                        break
            
            if page3_detected:
                self.logger.info("🪟 Meta ad consent popup detected (page 3 — ad experience)")
                if self._find_and_click(self.popup_selectors.ad_consent_ok_button, timeout=5):
                    self.logger.info("✅ Ad experience page dismissed (clicked OK)")
                    time.sleep(1.5)
                    return True
            
            return False
            
        except Exception as e:
            self.logger.warning(f"❌ Error handling ad consent popup: {e}")
            return False
