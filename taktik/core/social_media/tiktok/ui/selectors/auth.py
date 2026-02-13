"""Sélecteurs UI pour l'authentification et le login TikTok."""

from typing import List
from dataclasses import dataclass, field

TIKTOK_PACKAGE = "com.zhiliaoapp.musically"


@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login TikTok."""
    
    # === Champs de saisie (multilingue) ===
    username_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Email or username")]',
        '//android.widget.EditText[contains(@content-desc, "E-mail ou nom d\'utilisateur")]',
        '//android.widget.EditText[contains(@content-desc, "Phone number")]',
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
        '(//android.widget.EditText)[1]'
    ])
    
    password_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@content-desc, "Password")]',
        '//android.widget.EditText[contains(@content-desc, "Mot de passe")]',
        '//android.widget.EditText[@password="true"]',
        '(//android.widget.EditText)[2]'
    ])
    
    # === Boutons d'action (multilingue) ===
    login_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Log in"]',
        '//android.widget.Button[@content-desc="Se connecter"]',
        '//android.widget.Button[contains(@text, "Log in")]',
        '//android.widget.Button[contains(@text, "Se connecter")]',
    ])
    
    # === Détection de la page de login ===
    login_screen_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@content-desc, "TikTok")]',
        '//*[contains(@text, "Log in")]',
        '//*[contains(@text, "Sign up")]',
    ])


AUTH_SELECTORS = AuthSelectors()
