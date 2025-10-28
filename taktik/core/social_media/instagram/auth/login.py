"""
Module de login Instagram.

Gère le processus de connexion à Instagram avec support :
- Login classique (username/password)
- Détection et gestion des erreurs
- 2FA (à implémenter)
- Popups post-login
"""

import time
from typing import Optional, Tuple
from loguru import logger

from ..ui.selectors import AUTH_SELECTORS, POPUP_SELECTORS
from ..actions.atomic.text_actions import TextActions
from ..actions.atomic.click_actions import ClickActions
from ..actions.atomic.detection_actions import DetectionActions
from ..actions.core.utils import ActionUtils
from .session_manager import SessionManager


class LoginResult:
    """Résultat d'une tentative de login."""
    
    def __init__(
        self,
        success: bool,
        message: str,
        requires_2fa: bool = False,
        error_type: Optional[str] = None
    ):
        self.success = success
        self.message = message
        self.requires_2fa = requires_2fa
        self.error_type = error_type
    
    def __repr__(self):
        return f"LoginResult(success={self.success}, message='{self.message}')"


class InstagramLogin:
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
        # Dans ce cas, on considère que la connexion est réussie
        if is_on_login is False:
            # Vérifier si on est connecté (pas sur l'écran de login)
            time.sleep(2)
            for success_selector in self.auth_selectors.login_success_indicators:
                try:
                    if self.device.xpath(success_selector).exists:
                        self.logger.success("✅ Already logged in via saved profile!")
                        
                        # Gérer les popups post-login
                        self._handle_post_login_popups(save_login_info=save_login_info_instagram)
                        
                        # Sauvegarder la session si demandé
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
            
            # Si on n'est pas connecté, c'est une erreur
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
        time.sleep(3)  # Attendre la réponse du serveur
        
        # Étape 6: Détecter le résultat
        result = self._detect_login_result()
        
        # Étape 7: Gérer les popups post-login si succès
        if result.success:
            self._handle_post_login_popups(save_login_info=save_login_info_instagram)
            
            # Sauvegarder la session si demandé
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
            True si sur l'écran de login, False sinon
        """
        self.logger.debug("🔍 Checking if on login screen...")
        
        # Vérifier si on est sur l'écran de sélection de profil
        for selector in self.auth_selectors.profile_selection_screen:
            try:
                if self.device.xpath(selector).exists:
                    self.logger.info("📱 Detected profile selection screen")
                    
                    # Si on a un username cible, chercher le profil dans la liste
                    if target_username:
                        self.logger.info(f"🔍 Searching for profile: {target_username}")
                        
                        # Nettoyer le username (enlever @ et _ au début/fin)
                        clean_username = target_username.strip().lower().strip('@').strip('_')
                        
                        # Chercher tous les profils affichés
                        profile_selectors = [
                            f'//android.view.ViewGroup[contains(@content-desc, "{target_username}")]',
                            f'//android.view.ViewGroup[contains(@content-desc, "{clean_username}")]',
                            f'//*[@text="{target_username}"]',
                            f'//*[@text="{clean_username}"]',
                            f'//*[contains(@content-desc, "{target_username}") and @clickable="true"]',
                            f'//*[contains(@content-desc, "{clean_username}") and @clickable="true"]'
                        ]
                        
                        profile_found = False
                        for profile_selector in profile_selectors:
                            try:
                                profile_element = self.device.xpath(profile_selector)
                                if profile_element.exists:
                                    self.logger.success(f"✅ Found saved profile: {target_username}")
                                    profile_element.click()
                                    self.logger.success(f"✅ Clicked on profile: {target_username}")
                                    time.sleep(3)  # Attendre que le profil se connecte
                                    profile_found = True
                                    # Le profil est connecté, pas besoin de login
                                    return False  # On n'est pas sur l'écran de login, on est connecté
                            except Exception as e:
                                self.logger.debug(f"Profile selector failed: {e}")
                                continue
                        
                        if profile_found:
                            return False  # Profil trouvé et cliqué, pas besoin de login
                        
                        self.logger.info(f"⚠️ Profile {target_username} not found in saved profiles")
                    
                    # Profil non trouvé ou pas de username cible : cliquer sur "Use another profile"
                    self.logger.info("🔄 Clicking 'Use another profile'...")
                    use_another_selectors = [
                        '//android.widget.Button[@content-desc="Use another profile"]',
                        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
                        '//*[contains(@text, "Use another profile")]',
                        '//*[contains(@text, "Utiliser un autre profil")]'
                    ]
                    for use_selector in use_another_selectors:
                        btn = self.device.xpath(use_selector)
                        if btn.exists:
                            btn.click()
                            self.logger.success("✅ Clicked 'Use another profile'")
                            time.sleep(2)  # Attendre que l'écran de login apparaisse
                            break
                    break
            except:
                continue
        
        # Vérifier si on est maintenant sur l'écran de login
        for selector in self.auth_selectors.login_screen_indicators:
            try:
                if self.device.xpath(selector).exists:
                    self.logger.success("✅ On login screen")
                    return True
            except:
                continue
        
        self.logger.warning("⚠️ Not on login screen")
        return False
    
    def _fill_credentials(self, username: str, password: str) -> bool:
        """
        Remplit les champs username et password.
        
        Args:
            username: Nom d'utilisateur
            password: Mot de passe
            
        Returns:
            True si succès, False sinon
        """
        self.logger.info("📝 Filling credentials...")
        
        # Remplir le champ username
        username_filled = False
        for selector in self.auth_selectors.username_field:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"Found username field with selector: {selector}")
                    element.click()
                    time.sleep(self.utils.generate_human_like_delay(0.3, 0.6))
                    
                    if self.text_actions.type_text(username, clear_first=True, human_typing=True):
                        username_filled = True
                        self.logger.success("✅ Username filled")
                        break
            except Exception as e:
                self.logger.debug(f"Failed with selector {selector}: {e}")
                continue
        
        if not username_filled:
            self.logger.error("❌ Failed to fill username")
            return False
        
        # Petit délai entre les champs
        time.sleep(self.utils.generate_human_like_delay(0.5, 1.0))
        
        # Remplir le champ password
        password_filled = False
        for selector in self.auth_selectors.password_field:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"Found password field with selector: {selector}")
                    element.click()
                    time.sleep(self.utils.generate_human_like_delay(0.3, 0.6))
                    
                    if self.text_actions.type_text(password, clear_first=True, human_typing=True):
                        password_filled = True
                        self.logger.success("✅ Password filled")
                        break
            except Exception as e:
                self.logger.debug(f"Failed with selector {selector}: {e}")
                continue
        
        if not password_filled:
            self.logger.error("❌ Failed to fill password")
            return False
        
        return True
    
    def _click_login_button(self) -> bool:
        """
        Clique sur le bouton de connexion.
        
        Returns:
            True si succès, False sinon
        """
        self.logger.info("👆 Clicking login button...")
        
        # Petit délai avant de cliquer
        time.sleep(self.utils.generate_human_like_delay(0.5, 1.0))
        
        for selector in self.auth_selectors.login_button:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"Found login button with selector: {selector}")
                    element.click()
                    self.logger.success("✅ Login button clicked")
                    return True
            except Exception as e:
                self.logger.debug(f"Failed with selector {selector}: {e}")
                continue
        
        self.logger.error("❌ Failed to click login button")
        return False
    
    def _detect_login_result(self) -> LoginResult:
        """
        Détecte le résultat de la tentative de login.
        
        Returns:
            LoginResult avec le statut
        """
        self.logger.info("🔍 Detecting login result...")
        
        # Attendre un peu pour que la page charge
        time.sleep(2)
        
        # Vérifier si la popup "Save your login info?" est présente (indicateur de succès)
        save_login_popup_selectors = [
            '//android.view.View[@content-desc="Save your login info?"]',
            '//android.view.View[contains(@content-desc, "Save your login info")]',
            '//android.view.View[contains(@text, "Save your login info")]',
            '//android.view.View[contains(@content-desc, "Enregistrer vos informations")]',
            '//android.view.View[contains(@text, "Enregistrer vos informations")]'
        ]
        for selector in save_login_popup_selectors:
            try:
                if self.device.xpath(selector).exists:
                    self.logger.success("✅ Login successful! (Save login info popup detected)")
                    return LoginResult(
                        success=True,
                        message="Login successful"
                    )
            except:
                continue
        
        # Vérifier si connexion réussie
        for selector in self.auth_selectors.login_success_indicators:
            try:
                if self.device.xpath(selector).exists:
                    self.logger.success("✅ Login successful!")
                    return LoginResult(
                        success=True,
                        message="Login successful"
                    )
            except:
                continue
        
        # Vérifier si 2FA requis
        for selector in self.auth_selectors.two_factor_indicators:
            try:
                if self.device.xpath(selector).exists:
                    self.logger.warning("🔐 2FA required")
                    return LoginResult(
                        success=False,
                        message="2FA required (not yet implemented)",
                        requires_2fa=True,
                        error_type="2fa_required"
                    )
            except:
                continue
        
        # Vérifier si suspicious login
        for selector in self.auth_selectors.suspicious_login_indicators:
            try:
                if self.device.xpath(selector).exists:
                    self.logger.warning("⚠️ Suspicious login detected")
                    return LoginResult(
                        success=False,
                        message="Suspicious login - additional verification required",
                        error_type="suspicious_login"
                    )
            except:
                continue
        
        # Vérifier les messages d'erreur
        for selector in self.auth_selectors.error_message_selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    error_text = element.get_text()
                    self.logger.error(f"❌ Login error: {error_text}")
                    return LoginResult(
                        success=False,
                        message=f"Login failed: {error_text}",
                        error_type="credentials_error"
                    )
            except:
                continue
        
        # Si on est toujours sur l'écran de login
        if self._is_on_login_screen():
            self.logger.error("❌ Still on login screen - login failed")
            return LoginResult(
                success=False,
                message="Login failed - unknown error",
                error_type="unknown"
            )
        
        # Cas par défaut : on ne sait pas
        self.logger.warning("⚠️ Login result unclear, assuming failure")
        return LoginResult(
            success=False,
            message="Login result unclear",
            error_type="unclear"
        )
    
    def _handle_post_login_popups(self, save_login_info: bool = False) -> None:
        """
        Gère les popups qui apparaissent après une connexion réussie.
        
        Args:
            save_login_info: Si True, clique sur "Save", sinon sur "Not now"
        """
        self.logger.info("🪟 Handling post-login popups...")
        
        # Popup "Save Your Login Info"
        for selector in self.auth_selectors.save_login_info_popup:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.info("Found 'Save Login Info' popup")
                    
                    if save_login_info:
                        # Chercher le bouton "Save"
                        save_selectors = [
                            '//android.widget.Button[@content-desc="Save"]',
                            '//android.widget.Button[@content-desc="Enregistrer"]',
                            '//android.widget.Button[contains(@text, "Save")]',
                            '//android.widget.Button[contains(@text, "Enregistrer")]'
                        ]
                        for save_selector in save_selectors:
                            save_btn = self.device.xpath(save_selector)
                            if save_btn.exists:
                                save_btn.click()
                                self.logger.success("✅ Clicked 'Save' on login info popup")
                                time.sleep(1)
                                break
                    else:
                        # Chercher le bouton "Not Now"
                        for not_now_selector in self.popup_selectors.not_now_selectors:
                            not_now = self.device.xpath(not_now_selector)
                            if not_now.exists:
                                not_now.click()
                                self.logger.success("✅ Dismissed 'Save Login Info' popup (Not now)")
                                time.sleep(1)
                                break
                    break
            except:
                continue
        
        # Popup "Turn on Notifications"
        for selector in self.auth_selectors.notification_popup:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.info("Found 'Turn on Notifications' popup")
                    # Chercher le bouton "Not Now"
                    for not_now_selector in self.popup_selectors.not_now_selectors:
                        not_now = self.device.xpath(not_now_selector)
                        if not_now.exists:
                            not_now.click()
                            self.logger.success("✅ Dismissed 'Notifications' popup")
                            time.sleep(1)
                            break
                    break
            except:
                continue
        
        # Popup "Contacts Sync" (Find friends)
        for selector in self.auth_selectors.contacts_sync_popup:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.info("Found 'Contacts Sync' popup")
                    # Chercher le bouton "Ignorer" / "Skip"
                    skip_selectors = [
                        '//android.widget.Button[@content-desc="Ignorer"]',
                        '//android.widget.Button[@content-desc="Skip"]',
                        '//android.widget.Button[contains(@text, "Ignorer")]',
                        '//android.widget.Button[contains(@text, "Skip")]'
                    ]
                    for skip_selector in skip_selectors:
                        skip_btn = self.device.xpath(skip_selector)
                        if skip_btn.exists:
                            skip_btn.click()
                            self.logger.success("✅ Dismissed 'Contacts Sync' popup")
                            time.sleep(1)
                            break
                    break
            except:
                continue
        
        # Popup "Location Services"
        for selector in self.auth_selectors.location_services_popup:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.info("Found 'Location Services' popup")
                    # Cliquer sur "Continuer" / "Continue"
                    continue_selectors = [
                        '//android.widget.Button[@content-desc="Continuer"]',
                        '//android.widget.Button[@content-desc="Continue"]',
                        '//android.widget.Button[contains(@text, "Continuer")]',
                        '//android.widget.Button[contains(@text, "Continue")]'
                    ]
                    for continue_selector in continue_selectors:
                        continue_btn = self.device.xpath(continue_selector)
                        if continue_btn.exists:
                            continue_btn.click()
                            self.logger.success("✅ Clicked 'Continue' on Location Services popup")
                            time.sleep(1)
                            break
                    break
            except:
                continue
        
        # Permission système localisation (Android dialog)
        for selector in self.auth_selectors.location_permission_dialog:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.info("Found 'Location Permission' system dialog")
                    # Chercher le bouton "REFUSER" / "DENY"
                    deny_selectors = [
                        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
                        '//android.widget.Button[@text="REFUSER"]',
                        '//android.widget.Button[@text="DENY"]'
                    ]
                    for deny_selector in deny_selectors:
                        deny_btn = self.device.xpath(deny_selector)
                        if deny_btn.exists:
                            deny_btn.click()
                            self.logger.success("✅ Denied location permission")
                            time.sleep(1)
                            break
                    break
            except:
                continue
    
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
