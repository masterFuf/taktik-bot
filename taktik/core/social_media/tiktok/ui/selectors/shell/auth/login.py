"""Sélecteurs UI pour l'authentification et le login TikTok."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L

TIKTOK_PACKAGE = "com.zhiliaoapp.musically"


@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login TikTok."""

    # === Champs de saisie (multilingue) ===
    _username_field_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
        '(//android.widget.EditText)[1]'
    ])

    @property
    def username_field(self) -> List[str]:
        return self._username_field_base + L("auth.username_field")

    _password_field_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@password="true"]',
        '(//android.widget.EditText)[2]'
    ])

    @property
    def password_field(self) -> List[str]:
        return self._password_field_base + L("auth.password_field")

    # === Boutons d'action (multilingue) ===
    @property
    def login_button(self) -> List[str]:
        return L("auth.login_button")

    # === Détection de la page de login ===
    _login_screen_indicators_base: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "TikTok")]',
    ])

    @property
    def login_screen_indicators(self) -> List[str]:
        return self._login_screen_indicators_base + L("auth.login_screen_indicators")


AUTH_SELECTORS = AuthSelectors()
