"""Login screen detection and profile selection logic."""

import time


class LoginScreenDetectionMixin:
    """Mixin: détection écran de login + sélection intelligente de profil."""

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
        if self._element_exists(self.auth_selectors.login_screen_indicators):
            self.logger.success("✅ On login screen")
            return True
        
        self.logger.warning("⚠️ Not on login screen")
        return False
