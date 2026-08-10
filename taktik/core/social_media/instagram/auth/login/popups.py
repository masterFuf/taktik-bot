"""Post-login popup handling — save info, notifications, contacts, location."""

import time


class LoginPopupsMixin:
    """Mixin: post-login popup handling (save info, notifications, contacts, location)."""

    def _dismiss_google_autofill_popup(self) -> bool:
        """
        Detect and dismiss the password-manager or autofill popup that can
        appear when the app starts.

        Returns:
            True si le popup a été détecté et rejeté, False sinon.
        """
        if self._element_exists(self.auth_selectors.google_autofill_popup_indicators):
            self.logger.info("🔑 Google Password Manager popup detected — dismissing...")
            dismissed = self._click_first_match(
                self.auth_selectors.google_autofill_dismiss_button,
                "No thanks (GPM)"
            )
            if dismissed:
                self.logger.info("✅ Google autofill popup dismissed")
                time.sleep(1.5)
            else:
                self.logger.warning("⚠️ Could not dismiss Google autofill popup")
            return dismissed
        return False

    def _dismiss_google_save_password_popup(self) -> bool:
        """
        Detect and dismiss the Android save-password popup that appears after
        a successful login.

        Returns:
            True si détecté et rejeté, False sinon.
        """
        if self._element_exists(self.auth_selectors.google_save_password_indicators):
            self.logger.info("🔑 Google Save Password popup detected — dismissing...")
            dismissed = self._click_first_match(
                self.auth_selectors.google_save_password_no_button,
                "PAS MAINTENANT (Google save password)"
            )
            if dismissed:
                self.logger.info("✅ Google save password popup dismissed")
                time.sleep(1.0)
            else:
                self.logger.warning("⚠️ Could not dismiss Google save password popup")
            return dismissed
        return False

    def _handle_post_login_popups(self, save_login_info: bool = False) -> None:
        """
        Handle the popups appearing after a successful login.
        
        Args:
            save_login_info: when true, accept the save; otherwise decline
        """
        self.logger.info("🪟 Handling post-login popups...")

        # Google Password Manager / Autofill dialog (suggestions de remplissage)
        self._dismiss_google_autofill_popup()

        # System save-password dialog
        self._dismiss_google_save_password_popup()

        # Popup Instagram "Save Your Login Info?"
        if self._element_exists(self.auth_selectors.save_login_info_popup):
            self.logger.info(f"💾 'Save Your Login Info?' popup detected — save_login_info={save_login_info}")
            if save_login_info:
                clicked = self._click_first_match(self.auth_selectors.save_button_selectors, "Save")
                if clicked:
                    self.logger.info("✅ Clicked 'Save' — Instagram will remember login info")
                else:
                    self.logger.warning("⚠️ Could not click 'Save' button")
            else:
                # Decline button, matched by content-desc, which is more reliable here
                not_now_selectors = self.auth_selectors.save_login_info_not_now_buttons
                clicked = self._click_first_match(not_now_selectors, "Not now")
                if clicked:
                    self.logger.info("✅ Clicked 'Not now' — Instagram won't save login info")
                else:
                    self.logger.warning("⚠️ Could not click 'Not now' button")
            time.sleep(1)
        
        # Popup "Turn on Notifications"
        self._handle_popup(
            self.auth_selectors.notification_popup,
            self.popup_selectors.not_now_selectors,
            "Turn on Notifications", "Not now"
        )
        
        # Popup "Contacts Sync" (Find friends)
        self._handle_popup(
            self.auth_selectors.contacts_sync_popup,
            self.auth_selectors.skip_button_selectors,
            "Contacts Sync", "Skip"
        )
        
        # Popup "Location Services"
        self._handle_popup(
            self.auth_selectors.location_services_popup,
            self.auth_selectors.continue_button_selectors,
            "Location Services", "Continue"
        )
        
        # Permission système localisation (Android dialog)
        self._handle_popup(
            self.auth_selectors.location_permission_dialog,
            self.auth_selectors.deny_button_selectors,
            "Location Permission", "Deny"
        )
        
        # Meta Ad Consent popup (2-page flow)
        self._handle_ad_consent_popup()
    
    def _handle_ad_consent_popup(self) -> bool:
        """Handle the Meta ad consent popup (2-page flow).
        
        Page 1: Select "Use free of charge with ads" → Click "Continue"
        Page 2: Click "Agree"
        """
        try:
            # --- Page 1 ---
            if self._element_exists(self.popup_selectors.ad_consent_page1_indicators):
                self.logger.info("🪟 Meta ad consent popup detected (page 1)")
                
                # Select "Use free of charge with ads"
                self._click_first_match(
                    self.popup_selectors.ad_consent_free_option,
                    "Use free of charge with ads"
                )
                time.sleep(1)
                
                # Click "Continue"
                if self._click_first_match(
                    self.popup_selectors.ad_consent_continue_button,
                    "Continue"
                ):
                    time.sleep(2)
                else:
                    self.logger.warning("⚠️ Could not click Continue on ad consent page 1")
                    return False
            else:
                return False
            
            # --- Page 2 ---
            if self._element_exists(self.popup_selectors.ad_consent_page2_indicators):
                self.logger.info("🪟 Meta ad consent popup (page 2)")
                if self._click_first_match(
                    self.popup_selectors.ad_consent_agree_button,
                    "Agree"
                ):
                    self.logger.info("✅ Ad consent popup dismissed")
                    time.sleep(1.5)
            
            # --- Page 3: "You can manage your ad experience" → Click OK ---
            if self._element_exists(self.popup_selectors.ad_consent_page3_indicators):
                self.logger.info("🪟 Meta ad consent popup (page 3 — ad experience)")
                self._click_first_match(
                    self.popup_selectors.ad_consent_ok_button,
                    "OK"
                )
                time.sleep(1.5)
            
            return True
            
        except Exception as e:
            self.logger.warning(f"Error handling ad consent popup: {e}")
            return False
