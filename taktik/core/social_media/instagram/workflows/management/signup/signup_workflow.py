"""
Instagram account creation workflow.

Orchestrates the initial steps:
  1. Écran d'accueil non-connecté → clic "Create new account"
  2a. Écran téléphone → saisie numéro → Next
  2b. Ou basculer vers email → saisie email → Next

The later steps — name, date of birth, username, password, profile picture,
interests — need further UI dumps and are marked as pending.

"""

import time
from typing import Dict, Any, Optional
from loguru import logger

from ....auth.signup import InstagramSignup, SignupResult


class SignupWorkflow:
    """Full account creation workflow."""

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
        Start the account creation workflow.

        Args:
            method:  "email" ou "phone" — méthode d'inscription
            email:   Adresse e-mail (requis si method="email")
            phone:   phone number with its country code, required for the phone method

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

        # Validate the parameters
        if method == "email" and not email:
            result['message'] = "email is required when method='email'"
            result['error_type'] = "invalid_params"
            return result

        if method == "phone" and not phone:
            result['message'] = "phone is required when method='phone'"
            result['error_type'] = "invalid_params"
            return result

        # -- Step 1: navigate to the signup form --------------------------
        nav_result = self.signup_manager.navigate_to_signup()
        self._update_result(result, nav_result)
        if not nav_result.success:
            return result

        # -- Step 2a: signup by email -------------------------------------
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

        # -- Step 2b: signup by mobile number -----------------------------
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
        # The later steps — name, date of birth, username, password, profile
        # picture, interests — need further UI dumps.
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
