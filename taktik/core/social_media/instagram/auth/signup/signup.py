"""
Instagram signup — low-level actions for account creation flow.

Covers:
  - Home screen detection & navigation to signup
  - Phone-number signup screen: enter phone + Next
  - Email signup screen: enter email + Next
  - Switching between phone/email modes

Steps beyond phone/email capture (name, birthday, username, password, …)
are not yet automated and marked as TODO.
"""

import time
from typing import Optional
from loguru import logger

from ...ui.selectors.shell.auth import AUTH_SELECTORS
from ...actions.atomic.text import TextActions
from ...actions.core.utils import ActionUtils

from .models import SignupResult


class InstagramSignup:
    """Gestion de la création de compte Instagram (étapes initiales)."""

    def __init__(self, device, device_id: str):
        self.device = device
        self.device_id = device_id
        self.logger = logger.bind(module="instagram-signup")

        self.auth_selectors = AUTH_SELECTORS
        self.text_actions = TextActions(device)
        self.utils = ActionUtils()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def navigate_to_signup(self) -> SignupResult:
        """
        Depuis l'écran d'accueil non-connecté, clique sur "Create new account".

        Returns:
            SignupResult avec step="phone_input" ou step="email_input" si succès.
        """
        self.logger.info("🚀 Navigating to Instagram signup screen...")

        # Vérifier qu'on est bien sur l'écran d'accueil non-connecté
        if not self._is_on_home_logged_out_screen():
            return SignupResult(
                success=False,
                message="Not on Instagram home (logged-out) screen",
                step="home",
                error_type="wrong_screen"
            )

        # Cliquer sur "Create new account"
        if not self._click_first_match(
            self.auth_selectors.create_account_button,
            "Create new account"
        ):
            return SignupResult(
                success=False,
                message="Could not find 'Create new account' button",
                step="home",
                error_type="element_not_found"
            )

        time.sleep(2)

        # Détecter sur quel écran on atterrit
        step = self._detect_signup_step()
        return SignupResult(
            success=True,
            message=f"Reached signup screen: {step}",
            step=step
        )

    def enter_phone_number(self, phone: str) -> SignupResult:
        """
        Sur l'écran "What's your mobile number?", saisit le numéro et clique Next.

        Args:
            phone: Numéro de téléphone (ex: "+33600000000")
        """
        self.logger.info(f"📱 Entering phone number: {phone}")

        if not self._is_on_signup_phone_screen():
            return SignupResult(
                success=False,
                message="Not on phone-number input screen",
                step="phone_input",
                error_type="wrong_screen"
            )

        if not self._fill_field(self.auth_selectors.signup_phone_field, phone, "Phone field"):
            return SignupResult(
                success=False,
                message="Could not fill phone number field",
                step="phone_input",
                error_type="field_not_found"
            )

        time.sleep(self.utils.generate_human_like_delay(0.5, 1.0))

        if not self._click_first_match(self.auth_selectors.signup_next_button, "Next"):
            return SignupResult(
                success=False,
                message="Could not click Next button",
                step="phone_input",
                error_type="element_not_found"
            )

        time.sleep(2)
        return SignupResult(
            success=True,
            message="Phone number entered, moved to next step",
            step="after_phone"
        )

    def enter_email(self, email: str) -> SignupResult:
        """
        Sur l'écran "What's your email?", saisit l'email et clique Next.

        Args:
            email: Adresse e-mail (ex: "user@example.com")
        """
        self.logger.info(f"📧 Entering email: {email}")

        if not self._is_on_signup_email_screen():
            return SignupResult(
                success=False,
                message="Not on email input screen",
                step="email_input",
                error_type="wrong_screen"
            )

        if not self._fill_field(self.auth_selectors.signup_email_field, email, "Email field"):
            return SignupResult(
                success=False,
                message="Could not fill email field",
                step="email_input",
                error_type="field_not_found"
            )

        time.sleep(self.utils.generate_human_like_delay(0.5, 1.0))

        if not self._click_first_match(self.auth_selectors.signup_next_button, "Next"):
            return SignupResult(
                success=False,
                message="Could not click Next button",
                step="email_input",
                error_type="element_not_found"
            )

        time.sleep(2)
        return SignupResult(
            success=True,
            message="Email entered, moved to next step",
            step="after_email"
        )

    def switch_to_email_signup(self) -> bool:
        """Depuis l'écran téléphone, bascule vers inscription par e-mail."""
        return self._click_first_match(
            self.auth_selectors.signup_switch_to_email_button,
            "Sign up with email"
        )

    def switch_to_phone_signup(self) -> bool:
        """Depuis l'écran e-mail, bascule vers inscription par numéro de mobile."""
        return self._click_first_match(
            self.auth_selectors.signup_switch_to_phone_button,
            "Sign up with mobile number"
        )

    # ------------------------------------------------------------------
    # Screen detection helpers
    # ------------------------------------------------------------------

    def _is_on_home_logged_out_screen(self) -> bool:
        for selector in self.auth_selectors.home_logged_out_screen_indicators:
            try:
                if self.device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        return False

    def _is_on_signup_phone_screen(self) -> bool:
        for selector in self.auth_selectors.signup_phone_screen_indicators:
            try:
                if self.device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        return False

    def _is_on_signup_email_screen(self) -> bool:
        for selector in self.auth_selectors.signup_email_screen_indicators:
            try:
                if self.device.xpath(selector).exists:
                    return True
            except Exception:
                continue
        return False

    def _detect_signup_step(self) -> str:
        if self._is_on_signup_phone_screen():
            return "phone_input"
        if self._is_on_signup_email_screen():
            return "email_input"
        return "unknown"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _fill_field(self, selectors, value: str, label: str) -> bool:
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"Found {label} with selector: {selector}")
                    element.click()
                    time.sleep(self.utils.generate_human_like_delay(0.3, 0.6))
                    if self.text_actions.type_text(value, clear_first=True, human_typing=True):
                        self.logger.success(f"✅ {label} filled")
                        return True
            except Exception as e:
                self.logger.debug(f"{label} selector failed: {e}")
        self.logger.error(f"❌ Failed to fill {label}")
        return False

    def _click_first_match(self, selectors, label: str) -> bool:
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    element.click()
                    self.logger.success(f"✅ Clicked: {label}")
                    return True
            except Exception as e:
                self.logger.debug(f"Click selector failed ({label}): {e}")
        self.logger.error(f"❌ Could not click: {label}")
        return False
