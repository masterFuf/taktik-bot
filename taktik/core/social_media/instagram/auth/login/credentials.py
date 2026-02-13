"""Credential input — fill username/password fields and click login button."""

import time


class CredentialsMixin:
    """Mixin: saisie username/password + clic bouton de connexion."""

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
        
        if self._click_first_match(self.auth_selectors.login_button, "Login button"):
            return True
        
        self.logger.error("❌ Failed to click login button")
        return False
