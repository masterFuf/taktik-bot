"""Login screen detection and profile selection logic."""

import time
from typing import Any, List, Optional

from taktik.core.social_media.instagram.ui.selectors.shell.auth import AuthSelectors


class LoginScreenDetectionMixin:
    """Mixin: login screen detection and profile selection.

    Reading and acting are apart: `_read_login_screen` only reads which login screen is up;
    `_reach_login_form`, the login step, may tap a saved profile tile to get there.
    """

    # What the mixin reads from the class it is mixed into (`InstagramLogin`).
    device: Any
    logger: Any
    auth_selectors: AuthSelectors

    def _debug_snapshot(self, label: str) -> None:
        """Capture a screenshot and a UI dump for debugging, non-blocking."""
        try:
            import os, tempfile
            from taktik.core.shared.diagnostics.ui_dump_files import dump_ui_hierarchy, capture_screenshot
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

    def _first_present(self, selectors: List[str]) -> Optional[str]:
        """The first selector that finds something on the screen, or None. Reads only."""
        for selector in selectors:
            try:
                if self.device.xpath(selector).exists:
                    return selector
            except Exception as exc:
                self.logger.debug(f"Login screen selector failed ({selector}): {exc}")
        return None

    def _read_login_screen(self) -> Optional[str]:
        """Which login screen is up, read without touching anything.

        "profile_picker": the saved profiles ("Use another profile"); "login_form": the username
        and password form; None: neither (the home feed, a popup...). A check that must not act
        (the login result, the Lab's detection) reads this; only `_reach_login_form` taps.
        """
        picker = self._first_present(self.auth_selectors.profile_selection_screen)
        if picker:
            self.logger.debug(f"Saved profiles screen (selector: {picker})")
            return "profile_picker"
        form = self._first_present(self.auth_selectors.login_screen_indicators)
        if form:
            self.logger.debug(f"Login form (indicator: {form})")
            return "login_form"
        return None

    def _reach_login_form(self, target_username: str = None) -> Optional[bool]:
        """The login step before the credentials. On the saved profiles screen, tap the account's
        tile when it is saved, else "Use another profile"; then read whether the form is up.

        Args:
            target_username: the account to log in, used for the selection

        Returns:
            True when the login form is up; False when the account's saved tile was tapped (the
            home feed comes next); None when neither the form nor the saved profiles are up.
        """
        self.logger.info(f"🔍 Checking login screen state (target: @{target_username})...")
        self._debug_snapshot("before_screen_detection")

        if self._read_login_screen() == "profile_picker":
            self.logger.info("📱 Profile selection screen detected")
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

        if self._read_login_screen() == "login_form":
            self.logger.info("✅ Login screen confirmed")
            return True

        self.logger.warning("⚠️ Login screen NOT detected — returning None (screen unrecognized)")
        self._debug_snapshot("login_screen_not_detected")
        return None
