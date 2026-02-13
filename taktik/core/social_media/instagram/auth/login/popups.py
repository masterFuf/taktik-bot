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
