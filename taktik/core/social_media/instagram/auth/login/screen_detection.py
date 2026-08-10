"""Login screen detection and profile selection logic."""

import time


class LoginScreenDetectionMixin:
    """Mixin: login screen detection and profile selection."""

    def _debug_snapshot(self, label: str) -> None:
        """Capture a screenshot and a UI dump for debugging, non-blocking."""
        try:
            import os, tempfile
            from taktik.utils.ui_dump import dump_ui_hierarchy, capture_screenshot
            output_dir = os.path.join(tempfile.gettempdir(), 'taktik_debug')
            os.makedirs(output_dir, exist_ok=True)
            sc = capture_screenshot(self.device, output_dir)
            dump = dump_ui_hierarchy(self.device, output_dir)
            self.logger.info(f"📸 [{label}] Screenshot: {sc}")
            self.logger.info(f"📄 [{label}] UI Dump: {dump}")
        except Exception as e:
            self.logger.debug(f"Debug snapshot failed ({label}): {e}")

    def _log_all_clickable_elements(self) -> None:
        """Log every visible clickable element, for debugging."""
        try:
            elements = self.device.xpath(
                self.auth_selectors.clickable_visible_elements
            ).all()
            self.logger.info(f"🔍 Clickable elements on screen ({len(elements)} total):")
            for el in elements[:20]:  # Capped, to avoid flooding the logs
                try:
                    info = el.elem
                    cls = info.attrib.get('class', '?').split('.')[-1]
                    cd = info.attrib.get('content-desc', '')
                    txt = info.attrib.get('text', '')
                    rid = info.attrib.get('resource-id', '')
                    label = cd or txt or rid or '(no label)'
                    self.logger.info(f"   [{cls}] '{label}'")
                except Exception:
                    pass
        except Exception as e:
            self.logger.debug(f"Log clickable elements failed: {e}")

    def _is_on_login_screen(self, target_username: str = None) -> bool:
        """
        Check whether we are on the login screen.
        On the profile picker screen:
        - look for the requested profile in the list
        - Si trouvé : clique dessus directement
        - otherwise, tap the use-another-profile entry

        Args:
            target_username: the account to log in, used for the selection

        Returns:
            True on the login screen; False when a profile tile was tapped
        """
        self.logger.info(f"🔍 Checking login screen state (target: @{target_username})...")
        self._debug_snapshot("before_screen_detection")

        # Are we on the profile picker?
        matched_profile_selector = None
        for selector in self.auth_selectors.profile_selection_screen:
            try:
                if self.device.xpath(selector).exists:
                    matched_profile_selector = selector
                    break
            except Exception:
                continue

        if matched_profile_selector:
            self.logger.info(f"📱 Profile selection screen detected (selector: {matched_profile_selector})")
            self._log_all_clickable_elements()

            if target_username:
                self.logger.info(f"🔍 Searching for saved profile tile: '{target_username}'")
                clean_username = target_username.strip().lower().strip('@').strip('_')
                self.logger.info(f"🔍 Also trying clean variant: '{clean_username}'")

                profile_selectors = self.auth_selectors.saved_profile_tile_selectors(
                    target_username,
                    clean_username,
                )

                for profile_selector in profile_selectors:
                    try:
                        profile_element = self.device.xpath(profile_selector)
                        if profile_element.exists:
                            self.logger.info(f"✅ Found saved profile tile with: {profile_selector}")
                            profile_element.click()
                            self.logger.info(f"👆 Clicked profile tile @{target_username} — waiting for home screen...")
                            time.sleep(3)
                            return False
                        else:
                            self.logger.info(f"   ✗ Not found: {profile_selector}")
                    except Exception as e:
                        self.logger.info(f"   ✗ Selector error ({profile_selector}): {e}")
                        continue

                self.logger.info(f"⚠️ Profile tile @{target_username} NOT found in saved profiles — will use 'Use another profile'")

            # Profile not found, or no target given: tap the use-another-profile entry
            self.logger.info("🔄 Looking for 'Use another profile' button...")
            use_another_selectors = self.auth_selectors.use_another_profile_button
            clicked_use_another = False
            for use_selector in use_another_selectors:
                try:
                    btn = self.device.xpath(use_selector)
                    if btn.exists:
                        btn.click()
                        self.logger.info("✅ Clicked 'Use another profile' — waiting 3s for login screen...")
                        clicked_use_another = True
                        time.sleep(3)
                        self._dismiss_google_autofill_popup()
                        time.sleep(1)
                        self._debug_snapshot("after_use_another_profile")
                        self._log_all_clickable_elements()
                        break
                except Exception as e:
                    self.logger.debug(f"use_another selector failed: {e}")
            if not clicked_use_another:
                self.logger.warning("⚠️ 'Use another profile' button NOT found!")
        else:
            self.logger.info("🔍 No profile selection screen detected — checking for login screen directly...")

        # Are we on the login screen now?
        for indicator in self.auth_selectors.login_screen_indicators:
            try:
                if self.device.xpath(indicator).exists:
                    self.logger.info(f"✅ Login screen confirmed (indicator: {indicator})")
                    return True
            except Exception:
                continue

        self.logger.warning("⚠️ Login screen NOT detected — returning None (screen unrecognized)")
        self._debug_snapshot("login_screen_not_detected")
        return None
