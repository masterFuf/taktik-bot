"""
Login process facade — composes all login mixins.

Sub-modules:
- models.py            — LoginResult data class
- screen_detection.py  — login screen detection and profile selection
- credentials.py       — username and password entry, then the login tap
- result_detection.py  — Détection succès/erreur/2FA après login
- popups.py            — Gestion popups post-login (save info, notifs, contacts)
"""

import time
from typing import Optional, Tuple
from loguru import logger

from ...ui.selectors.shell.auth import AUTH_SELECTORS
from ...ui.selectors.shell.popups import POPUP_SELECTORS
from ...actions.atomic.text import TextActions
from ...actions.atomic.interaction import ClickActions
from ...actions.atomic.detection import DetectionActions
from ...actions.core.utils import ActionUtils

from .models import LoginResult
from .screen_detection import LoginScreenDetectionMixin
from .credentials import CredentialsMixin
from .result_detection import ResultDetectionMixin
from .popups import LoginPopupsMixin
from ..session import SessionManager
from taktik.core.shared.device.wait import find_element


class InstagramLogin(
    LoginScreenDetectionMixin,
    CredentialsMixin,
    ResultDetectionMixin,
    LoginPopupsMixin
):
    """Gestionnaire de connexion Instagram."""
    
    def __init__(self, device, device_id: str):
        """
        Initialise the login manager.
        
        Args:
            device: the device instance
            device_id: the device identifier
        """
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-login")
        
        # Sélecteurs
        self.auth_selectors = AUTH_SELECTORS
        self.popup_selectors = POPUP_SELECTORS
        
        # Actions atomiques
        self.text_actions = TextActions(device)
        self.click_actions = ClickActions(device)
        self.detection_actions = DetectionActions(device)
        self.utils = ActionUtils()
        
        # Session manager
        self.session_manager = SessionManager()
    
    def _find_element(self, selectors: list) -> object:
        """Find first matching element from a list of xpath selectors."""
        return find_element(self.device, selectors)
    
    def _click_first_match(self, selectors: list, element_name: str) -> bool:
        """Click first matching element from a list of xpath selectors."""
        element = self._find_element(selectors)
        if element:
            element.click()
            self.logger.success(f"✅ Clicked '{element_name}'")
            return True
        return False
    
    def _element_exists(self, selectors: list) -> bool:
        """Check if any element from selectors exists."""
        return self._find_element(selectors) is not None
    
    def _handle_popup(self, popup_selectors: list, button_selectors: list, 
                      popup_name: str, button_name: str) -> bool:
        """Handle a popup by detecting it and clicking a dismiss button."""
        if self._element_exists(popup_selectors):
            self.logger.info(f"Found '{popup_name}' popup")
            if self._click_first_match(button_selectors, button_name):
                time.sleep(1)
                return True
        return False
    
    def login(
        self,
        username: str,
        password: str,
        save_session: bool = True,
        use_saved_session: bool = True,
        save_login_info_instagram: bool = False
    ) -> LoginResult:
        """
        Connecte un utilisateur à Instagram.
        
        Args:
            username: Nom d'utilisateur, email ou numéro de téléphone
            password: the password
            save_session: save our own session record after a successful login
            use_saved_session: try to reuse one of our saved session records
            save_login_info_instagram: answer the app's own save-credentials popup
            
        Returns:
            LoginResult carrying the login status
        """
        self.logger.info(f"🔐 Starting login process for {username}")
        
        # Step 0: dismiss the password-manager popup when present
        self._dismiss_google_autofill_popup()
        
        # Step 1: is there a saved session?
        if use_saved_session:
            session = self.session_manager.load_session(username, self.device_id)
            if session:
                self.logger.info("📦 Found saved session, attempting to restore...")
                # TODO: implement session restoration
                # For now, fall through to the regular login
        
        # Step 2: confirm the login screen, with the profile selection
        is_on_login = self._is_on_login_screen(target_username=username)

        # None means an unrecognised screen, neither login nor profile picker: give up
        if is_on_login is None:
            self.logger.warning("⚠️ Screen not recognized after launch — aborting attempt")
            return LoginResult(
                success=False,
                message="Screen not recognized after Instagram launch",
                error_type="wrong_screen"
            )

        # False means the saved profile was found and tapped, so wait for the home feed,
        # handling the popups that may come in between.
        if is_on_login is False:
            self.logger.info("⏳ Profile tile clicked — waiting for home screen...")
            logged_in_via_profile = False

            for attempt in range(6):          # jusqu'à ~12 secondes
                time.sleep(2)

                # Is the home screen visible?
                for success_selector in self.auth_selectors.login_success_indicators:
                    try:
                        if self.device.xpath(success_selector).exists:
                            logged_in_via_profile = True
                            break
                    except Exception:
                        continue

                if logged_in_via_profile:
                    break

                # Popup intermédiaire possible — on tente de les fermer
                self.logger.debug(f"🔄 Attempt {attempt + 1}/6 — checking for blocking popups...")
                self._dismiss_google_autofill_popup()
                self._handle_post_login_popups(save_login_info=save_login_info_instagram)

            if logged_in_via_profile:
                self.logger.success("✅ Already logged in via saved profile!")

                self._handle_post_login_popups(save_login_info=save_login_info_instagram)

                if save_session:
                    self.session_manager.save_session(
                        username=username,
                        device_id=self.device_id,
                        session_data={
                            'username': username,
                            'login_method': 'saved_profile',
                            'device_info': self._get_device_info()
                        }
                    )

                return LoginResult(
                    success=True,
                    message="Logged in via saved profile"
                )

            # Did we land on a password-entry screen? Instagram sometimes asks for a
            # password confirmation after a profile tap.
            if self._element_exists(self.auth_selectors.password_only_screen_indicators):
                self.logger.info("🔐 Password confirmation required after profile click — filling password...")
                # Carry on with the credentials entry
                is_on_login = True
            else:
                self.logger.error("❌ Home screen not detected after profile click")
                return LoginResult(
                    success=False,
                    message="Login via saved profile failed: home screen not found",
                    error_type="wrong_screen"
                )
        
        # Step 3: fill the fields
        if not self._fill_credentials(username, password):
            return LoginResult(
                success=False,
                message="Failed to fill credentials",
                error_type="input_error"
            )
        
        # Step 4: tap the login button
        if not self._click_login_button():
            return LoginResult(
                success=False,
                message="Failed to click login button",
                error_type="button_error"
            )
        
        # Step 5: wait, then check the result
        self.logger.info("⏳ Waiting for login response...")
        time.sleep(3)
        
        # Step 6: detect the result
        result = self._detect_login_result()
        
        # Step 7: handle the post-login popups on success
        if result.success:
            self._handle_post_login_popups(save_login_info=save_login_info_instagram)
            
            if save_session:
                self.session_manager.save_session(
                    username=username,
                    device_id=self.device_id,
                    session_data={
                        'username': username,
                        'login_method': 'password',
                        'device_info': self._get_device_info()
                    }
                )
        
        return result
    
    def _get_device_info(self) -> dict:
        """
        Read the device information.
        
        Returns:
            Dict of device information
        """
        try:
            info = self.device.device_info
            return {
                'device_id': self.device_id,
                'model': info.get('model', 'unknown'),
                'brand': info.get('brand', 'unknown'),
                'android_version': info.get('version', 'unknown')
            }
        except Exception:
            return {
                'device_id': self.device_id,
                'model': 'unknown',
                'brand': 'unknown',
                'android_version': 'unknown'
            }
    
    def logout(self) -> bool:
        """
        Déconnecte l'utilisateur (à implémenter).
        
        Returns:
            True si succès, False sinon
        """
        # TODO: implement the logout
        self.logger.warning("⚠️ Logout not yet implemented")
        return False


__all__ = ['InstagramLogin', 'LoginResult']
