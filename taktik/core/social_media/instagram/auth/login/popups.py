"""Post-login popup handling — save info, notifications, contacts, location."""

import time


class LoginPopupsMixin:
    """Mixin: gestion des popups post-login (save info, notifs, contacts, localisation)."""

    def _handle_post_login_popups(self, save_login_info: bool = False) -> None:
        """
        Gère les popups qui apparaissent après une connexion réussie.
        
        Args:
            save_login_info: Si True, clique sur "Save", sinon sur "Not now"
        """
        self.logger.info("🪟 Handling post-login popups...")
        
        # Popup "Save Your Login Info"
        if self._element_exists(self.auth_selectors.save_login_info_popup):
            self.logger.info("Found 'Save Login Info' popup")
            if save_login_info:
                self._click_first_match(self.auth_selectors.save_button_selectors, "Save")
            else:
                self._click_first_match(self.popup_selectors.not_now_selectors, "Not now")
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
