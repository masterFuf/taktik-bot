"""Login screen detection and profile selection logic."""

import time


class LoginScreenDetectionMixin:
    """Mixin: détection écran de login + sélection intelligente de profil."""

    def _debug_snapshot(self, label: str) -> None:
        """Capture screenshot + UI dump pour debug (non bloquant)."""
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
        """Log tous les éléments cliquables visibles pour debug."""
        try:
            elements = self.device.xpath('//*[@clickable="true" and @visible-to-user="true"]').all()
            self.logger.info(f"🔍 Clickable elements on screen ({len(elements)} total):")
            for el in elements[:20]:  # Limiter à 20 pour ne pas spammer
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
        Vérifie si on est sur l'écran de login.
        Si on est sur l'écran de sélection de profil :
        - Cherche le profil demandé dans la liste
        - Si trouvé : clique dessus directement
        - Sinon : clique sur "Use another profile"

        Args:
            target_username: Username du compte à connecter (pour sélection intelligente)

        Returns:
            True si sur l'écran de login, False si profil tile cliqué (connecté ou en cours)
        """
        self.logger.info(f"🔍 Checking login screen state (target: @{target_username})...")
        self._debug_snapshot("before_screen_detection")

        # Vérifier si on est sur l'écran de sélection de profil
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

                profile_selectors = [
                    f'//android.view.ViewGroup[contains(@content-desc, "{target_username}")]',
                    f'//android.view.ViewGroup[contains(@content-desc, "{clean_username}")]',
                    f'//*[@text="{target_username}"]',
                    f'//*[@text="{clean_username}"]',
                    f'//*[contains(@content-desc, "{target_username}") and @clickable="true"]',
                    f'//*[contains(@content-desc, "{clean_username}") and @clickable="true"]'
                ]

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

            # Profil non trouvé ou pas de username cible : cliquer sur "Use another profile"
            self.logger.info("🔄 Looking for 'Use another profile' button...")
            use_another_selectors = [
                '//android.widget.Button[@content-desc="Use another profile"]',
                '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
                '//*[contains(@text, "Use another profile")]',
                '//*[contains(@text, "Utiliser un autre profil")]'
            ]
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

        # Vérifier si on est maintenant sur l'écran de login
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
