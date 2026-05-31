"""Login result detection — detect success, 2FA, errors after login attempt."""

import time

from .models import LoginResult


class ResultDetectionMixin:
    """Mixin: détection du résultat de login (succès, 2FA, erreur, suspicious)."""

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
        save_login_popup_selectors = self.auth_selectors.save_login_info_success_popup
        if self._element_exists(save_login_popup_selectors):
            self.logger.success("✅ Login successful! (Save login info popup detected)")
            return LoginResult(success=True, message="Login successful")
        
        # Vérifier si connexion réussie
        if self._element_exists(self.auth_selectors.login_success_indicators):
            self.logger.success("✅ Login successful!")
            return LoginResult(success=True, message="Login successful")
        
        # Vérifier si 2FA requis
        if self._element_exists(self.auth_selectors.two_factor_indicators):
            self.logger.warning("🔐 2FA required")
            return LoginResult(
                success=False, message="2FA required (not yet implemented)",
                requires_2fa=True, error_type="2fa_required"
            )
        
        # Vérifier si suspicious login
        if self._element_exists(self.auth_selectors.suspicious_login_indicators):
            self.logger.warning("⚠️ Suspicious login detected")
            return LoginResult(
                success=False, message="Suspicious login - additional verification required",
                error_type="suspicious_login"
            )
        
        # Vérifier les messages d'erreur
        error_element = self._find_element(self.auth_selectors.error_message_selectors)
        if error_element:
            error_text = error_element.get_text()
            self.logger.error(f"❌ Login error: {error_text}")
            return LoginResult(
                success=False, message=f"Login failed: {error_text}",
                error_type="credentials_error"
            )
        
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
