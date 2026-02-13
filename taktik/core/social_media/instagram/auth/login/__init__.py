"""
Login process facade — composes all login mixins.

Sub-modules:
- models.py            — LoginResult data class
- screen_detection.py  — Détection écran login + sélection profil
- credentials.py       — Saisie username/password + clic bouton login
- result_detection.py  — Détection succès/erreur/2FA après login
- popups.py            — Gestion popups post-login (save info, notifs, contacts)
"""

import time
from typing import Optional, Tuple
from loguru import logger

from ...ui.selectors import AUTH_SELECTORS, POPUP_SELECTORS
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


class InstagramLogin(
    LoginScreenDetectionMixin,
    CredentialsMixin,
    ResultDetectionMixin,
    LoginPopupsMixin
):
    """Gestionnaire de connexion Instagram."""
    
    def __init__(self, device, device_id: str):
        """
        Initialise le gestionnaire de login.
        
        Args:
            device: Instance du device (uiautomator2)
            device_id: ID du device (ADB ID)
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
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    return element
            except:
                continue
        return None
    
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
            password: Mot de passe
            save_session: Sauvegarder la session après connexion réussie (notre système)
            use_saved_session: Tenter d'utiliser une session sauvegardée (notre système)
            save_login_info_instagram: Sauvegarder les infos de login dans Instagram (popup Instagram)
            
        Returns:
            LoginResult avec le statut de la connexion
        """
        self.logger.info(f"🔐 Starting login process for {username}")
        
        # Étape 1: Vérifier si une session existe
        if use_saved_session:
            session = self.session_manager.load_session(username, self.device_id)
            if session:
                self.logger.info("📦 Found saved session, attempting to restore...")
                # TODO: Implémenter la restauration de session
                # Pour l'instant, on continue avec le login classique
        
        # Étape 2: Vérifier qu'on est sur l'écran de login (avec sélection intelligente de profil)
        is_on_login = self._is_on_login_screen(target_username=username)
        
        # Si False est retourné, cela peut signifier que le profil a été trouvé et cliqué
        if is_on_login is False:
            time.sleep(2)
            for success_selector in self.auth_selectors.login_success_indicators:
                try:
                    if self.device.xpath(success_selector).exists:
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
                except:
                    continue
            
            self.logger.error("❌ Not on login screen")
            return LoginResult(
                success=False,
                message="Not on login screen",
                error_type="wrong_screen"
            )
        
        # Étape 3: Remplir les champs
        if not self._fill_credentials(username, password):
            return LoginResult(
                success=False,
                message="Failed to fill credentials",
                error_type="input_error"
            )
        
        # Étape 4: Cliquer sur le bouton de connexion
        if not self._click_login_button():
            return LoginResult(
                success=False,
                message="Failed to click login button",
                error_type="button_error"
            )
        
        # Étape 5: Attendre et vérifier le résultat
        self.logger.info("⏳ Waiting for login response...")
        time.sleep(3)
        
        # Étape 6: Détecter le résultat
        result = self._detect_login_result()
        
        # Étape 7: Gérer les popups post-login si succès
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
        Récupère les informations du device.
        
        Returns:
            Dictionnaire avec les infos du device
        """
        try:
            info = self.device.device_info
            return {
                'device_id': self.device_id,
                'model': info.get('model', 'unknown'),
                'brand': info.get('brand', 'unknown'),
                'android_version': info.get('version', 'unknown')
            }
        except:
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
        # TODO: Implémenter la déconnexion
        self.logger.warning("⚠️ Logout not yet implemented")
        return False


__all__ = ['InstagramLogin', 'LoginResult']
