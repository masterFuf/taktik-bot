from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login Instagram."""
    
    # === Champs de saisie (multilingue) ===
    username_field: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.EditText[contains(@content-desc, "Username, email or mobile number")]',
        # Sélecteur par content-desc (français)
        '//android.widget.EditText[contains(@content-desc, "Nom de profil, e-mail ou numéro de mobile")]',
        # Sélecteur générique par classe
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
        # Fallback par position (premier EditText)
        '(//android.widget.EditText)[1]'
    ])
    
    password_field: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.EditText[contains(@content-desc, "Password")]',
        # Sélecteur par content-desc (français)
        '//android.widget.EditText[contains(@content-desc, "Mot de passe")]',
        # Sélecteur par attribut password
        '//android.widget.EditText[@password="true"]',
        # Fallback par position (second EditText)
        '(//android.widget.EditText)[2]'
    ])
    
    # === Boutons d'action (multilingue) ===
    login_button: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.Button[@content-desc="Log in"]',
        # Sélecteur par content-desc (français)
        '//android.widget.Button[@content-desc="Se connecter"]',
        # Sélecteur par texte visible (anglais)
        '//android.widget.Button[.//android.view.View[@content-desc="Log in"]]',
        # Sélecteur par texte visible (français)
        '//android.widget.Button[.//android.view.View[@content-desc="Se connecter"]]',
        # Fallback générique (premier bouton cliquable après les champs)
        '(//android.widget.Button[@clickable="true"])[1]'
    ])
    
    create_account_button: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.Button[@content-desc="Create new account"]',
        # Sélecteur par content-desc (français)
        '//android.widget.Button[@content-desc="Créer un compte"]',
        # Sélecteur par texte visible (anglais)
        '//android.widget.Button[.//android.view.View[@content-desc="Create new account"]]',
        # Sélecteur par texte visible (français)
        '//android.widget.Button[.//android.view.View[@content-desc="Créer un compte"]]'
    ])
    
    forgot_password_button: List[str] = field(default_factory=lambda: [
        # Sélecteur par content-desc (anglais)
        '//android.widget.Button[@content-desc="Forgot password?"]',
        # Sélecteur par content-desc (français)
        '//android.widget.Button[@content-desc="Mot de passe oublié ?"]',
        # Sélecteur par texte visible (anglais)
        '//android.widget.Button[.//android.view.View[@content-desc="Forgot password?"]]',
        # Sélecteur par texte visible (français)
        '//android.widget.Button[.//android.view.View[@content-desc="Mot de passe oublié ?"]]'
    ])
    
    # === Détection de la page de login ===
    login_screen_indicators: List[str] = field(default_factory=lambda: [
        # Logo Instagram
        '//android.widget.ImageView[@content-desc="Instagram from Meta"]',
        # Sélecteur de langue
        '//android.widget.Button[contains(@content-desc, "English") or contains(@content-desc, "Français")]',
        # Présence simultanée des champs username et password
        '//android.widget.EditText[@password="false"]/following-sibling::*//android.widget.EditText[@password="true"]'
    ])
    
    # === Écran de sélection de profil (comptes enregistrés) ===
    profile_selection_screen: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Use another profile"]',
        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
        '//android.widget.Button[@content-desc="Create new account"]',
        '//android.widget.Button[@content-desc="Créer un compte"]',
        '//*[contains(@text, "Use another profile")]',
        '//*[contains(@text, "Utiliser un autre profil")]'
    ])
    
    # === Messages d'erreur et états ===
    error_message_selectors: List[str] = field(default_factory=lambda: [
        # Messages d'erreur génériques
        '//android.widget.TextView[contains(@text, "incorrect")]',
        '//android.widget.TextView[contains(@text, "Incorrect")]',
        '//android.widget.TextView[contains(@text, "incorrecte")]',
        '//android.widget.TextView[contains(@text, "Incorrecte")]',
        # Compte bloqué/suspendu
        '//android.widget.TextView[contains(@text, "suspended")]',
        '//android.widget.TextView[contains(@text, "blocked")]',
        '//android.widget.TextView[contains(@text, "suspendu")]',
        '//android.widget.TextView[contains(@text, "bloqué")]',
        # Trop de tentatives
        '//android.widget.TextView[contains(@text, "too many")]',
        '//android.widget.TextView[contains(@text, "trop de")]',
        '//android.widget.TextView[contains(@text, "Try again")]',
        '//android.widget.TextView[contains(@text, "Réessayer")]'
    ])
    
    # === 2FA et vérification ===
    two_factor_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "security code")]',
        '//android.widget.TextView[contains(@text, "code de sécurité")]',
        '//android.widget.TextView[contains(@text, "verification")]',
        '//android.widget.TextView[contains(@text, "vérification")]',
        '//android.widget.EditText[contains(@hint, "code")]'
    ])
    
    two_factor_code_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "code")]',
        '//android.widget.EditText[contains(@hint, "Code")]',
        '(//android.widget.EditText)[1]'
    ])
    
    two_factor_confirm_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@text, "Confirm")]',
        '//android.widget.Button[contains(@text, "Confirmer")]',
        '//android.widget.Button[contains(@text, "Next")]',
        '//android.widget.Button[contains(@text, "Suivant")]'
    ])
    
    # === Suspicious login / Vérification supplémentaire ===
    suspicious_login_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "We detected")]',
        '//android.widget.TextView[contains(@text, "Nous avons détecté")]',
        '//android.widget.TextView[contains(@text, "unusual")]',
        '//android.widget.TextView[contains(@text, "inhabituel")]',
        '//android.widget.TextView[contains(@text, "verify")]',
        '//android.widget.TextView[contains(@text, "vérifier")]'
    ])
    
    # === Popups post-login (Save login info, Turn on notifications, etc.) ===
    save_login_info_popup: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Save Your Login Info")]',
        '//android.widget.TextView[contains(@text, "Enregistrer vos informations")]',
        '//android.widget.Button[contains(@text, "Save")]',
        '//android.widget.Button[contains(@text, "Enregistrer")]',
        '//android.widget.Button[contains(@text, "Not Now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]'
    ])
    
    notification_popup: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Turn on Notifications")]',
        '//android.widget.TextView[contains(@text, "Activer les notifications")]',
        '//android.widget.Button[contains(@text, "Turn On")]',
        '//android.widget.Button[contains(@text, "Activer")]',
        '//android.widget.Button[contains(@text, "Not Now")]',
        '//android.widget.Button[contains(@text, "Pas maintenant")]'
    ])
    
    # === Popup contacts (Find friends) ===
    contacts_sync_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Autorisez l\'accès à vos contacts")]',
        '//*[contains(@text, "Allow access to your contacts")]',
        '//*[contains(@text, "Find friends")]',
        '//*[contains(@text, "Trouver des amis")]',
        '//android.widget.Button[@content-desc="Autoriser"]',
        '//android.widget.Button[@content-desc="Allow"]',
        '//android.widget.Button[@content-desc="Ignorer"]',
        '//android.widget.Button[@content-desc="Skip"]'
    ])
    
    # === Popup localisation (Location services) ===
    location_services_popup: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Pour utiliser les Services de localisation")]',
        '//*[contains(@text, "To use Location Services")]',
        '//*[contains(@text, "Services de localisation")]',
        '//*[contains(@text, "Location Services")]',
        '//android.widget.Button[@content-desc="Continuer"]',
        '//android.widget.Button[@content-desc="Continue"]'
    ])
    
    # === Permission système localisation (Android system dialog) ===
    location_permission_dialog: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Permettre à Instagram d\'accéder à la position")]',
        '//*[contains(@text, "Allow Instagram to access this device\'s location")]',
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_allow_button"]',
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//android.widget.Button[@text="AUTORISER"]',
        '//android.widget.Button[@text="ALLOW"]',
        '//android.widget.Button[@text="REFUSER"]',
        '//android.widget.Button[@text="DENY"]'
    ])
    
    # === Boutons génériques pour popups ===
    save_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Save"]',
        '//android.widget.Button[@content-desc="Enregistrer"]',
        '//android.widget.Button[contains(@text, "Save")]',
        '//android.widget.Button[contains(@text, "Enregistrer")]'
    ])
    
    skip_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Ignorer"]',
        '//android.widget.Button[@content-desc="Skip"]',
        '//android.widget.Button[contains(@text, "Ignorer")]',
        '//android.widget.Button[contains(@text, "Skip")]'
    ])
    
    continue_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Continuer"]',
        '//android.widget.Button[@content-desc="Continue"]',
        '//android.widget.Button[contains(@text, "Continuer")]',
        '//android.widget.Button[contains(@text, "Continue")]'
    ])
    
    deny_button_selectors: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//android.widget.Button[@text="REFUSER"]',
        '//android.widget.Button[@text="DENY"]'
    ])
    
    # === Détection de connexion réussie ===
    login_success_indicators: List[str] = field(default_factory=lambda: [
        # Navigation bar visible (home, search, etc.)
        '//*[contains(@content-desc, "Home") or contains(@content-desc, "Accueil")]',
        '//*[contains(@content-desc, "Search") or contains(@content-desc, "Rechercher")]',
        # Feed timeline
        '//*[@resource-id="com.instagram.android:id/feed_timeline"]',
        # Profile tab accessible
        '//*[contains(@resource-id, "profile_tab")]'
    ])

AUTH_SELECTORS = AuthSelectors()
