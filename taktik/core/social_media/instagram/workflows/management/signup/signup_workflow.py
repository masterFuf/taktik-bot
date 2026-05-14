"""
Workflow de création de compte Instagram.

Orchestre les étapes initiales :
  1. Écran d'accueil non-connecté → clic "Create new account"
  2a. Écran téléphone → saisie numéro → Next
  2b. Ou basculer vers email → saisie email → Next

Les étapes suivantes (nom, date de naissance, username, mot de passe,
photo de profil, centres d'intérêt, …) nécessitent des dumps UI
supplémentaires et sont marquées TODO.
"""

import time
from typing import Dict, Any, Optional
from loguru import logger

from ....auth.signup import InstagramSignup, SignupResult


class SignupWorkflow:
    """Workflow complet de création de compte Instagram."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-signup-workflow")

        self.signup_manager = InstagramSignup(device, device_id)

    def execute(
        self,
        method: str = "email",
        email: Optional[str] = None,
        phone: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Lance le workflow de création de compte.

        Args:
            method:  "email" ou "phone" — méthode d'inscription
            email:   Adresse e-mail (requis si method="email")
            phone:   Numéro de téléphone avec indicatif (requis si method="phone")

        Returns:
            {
                'success': bool,
                'step':    str,   # dernière étape atteinte
                'message': str,
                'error_type': str | None
            }
        """
        self.logger.info(
            f"🚀 Starting signup workflow — method={method}"
        )

        result: Dict[str, Any] = {
            'success': False,
            'step': 'init',
            'message': '',
            'error_type': None
        }

        # Validation des paramètres
        if method == "email" and not email:
            result['message'] = "email is required when method='email'"
            result['error_type'] = "invalid_params"
            return result

        if method == "phone" and not phone:
            result['message'] = "phone is required when method='phone'"
            result['error_type'] = "invalid_params"
            return result

        # ── Étape 1 : naviguer vers le formulaire d'inscription ──────────
        nav_result = self.signup_manager.navigate_to_signup()
        self._update_result(result, nav_result)
        if not nav_result.success:
            return result

        # ── Étape 2a : inscription par email ─────────────────────────────
        if method == "email":
            # Si on atterrit sur l'écran téléphone, basculer vers email
            if nav_result.step == "phone_input":
                self.logger.info("📧 Switching to email signup...")
                if not self.signup_manager.switch_to_email_signup():
                    result['success'] = False
                    result['step'] = "phone_input"
                    result['message'] = "Could not switch to email signup"
                    result['error_type'] = "element_not_found"
                    return result
                time.sleep(1.5)

            email_result = self.signup_manager.enter_email(email)
            self._update_result(result, email_result)
            if not email_result.success:
                return result

        # ── Étape 2b : inscription par numéro de mobile ──────────────────
        elif method == "phone":
            # Si on atterrit sur l'écran email, basculer vers téléphone
            if nav_result.step == "email_input":
                self.logger.info("📱 Switching to phone signup...")
                if not self.signup_manager.switch_to_phone_signup():
                    result['success'] = False
                    result['step'] = "email_input"
                    result['message'] = "Could not switch to phone signup"
                    result['error_type'] = "element_not_found"
                    return result
                time.sleep(1.5)

            phone_result = self.signup_manager.enter_phone_number(phone)
            self._update_result(result, phone_result)
            if not phone_result.success:
                return result

        # ── Étapes suivantes (TODO) ───────────────────────────────────────
        # Les étapes suivantes (nom, date de naissance, username, password,
        # photo de profil, intérêts) nécessitent des UI dumps supplémentaires.
        self.logger.warning(
            "⚠️ Signup workflow: further steps (name, birthday, username, "
            "password, …) are not yet implemented."
        )
        result['message'] += " | Next steps (name/birthday/username/…) not yet implemented"

        return result

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _update_result(result: Dict[str, Any], step_result: SignupResult) -> None:
        result['success'] = step_result.success
        result['step'] = step_result.step
        result['message'] = step_result.message
        result['error_type'] = step_result.error_type
