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
        # Sélecteur générique par classe (exclut le champ password pour éviter faux positifs)
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
    ])

    # Bouton X/effacer qui apparaît à côté du champ username quand il est focalisé et pré-rempli
    username_clear_button: List[str] = field(default_factory=lambda: [
        # Anglais
        '//android.widget.ImageView[@content-desc="Clear Username, email or mobile number text"]',
        '//android.widget.ImageView[contains(@content-desc, "Clear") and contains(@content-desc, "Username")]',
        # Français
        '//android.widget.ImageView[contains(@content-desc, "Vider") and contains(@content-desc, "Nom de profil")]',
        '//android.widget.ImageView[contains(@content-desc, "Effacer") and contains(@content-desc, "Nom de profil")]',
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
        # Sur l'écran d'accueil (non connecté), c'est un View et non un Button
        '//android.view.View[@content-desc="Create new account"]',
        '//android.view.View[@content-desc="Créer un compte"]',
        # Fallback Button (ancienne version de l'app)
        '//android.widget.Button[@content-desc="Create new account"]',
        '//android.widget.Button[@content-desc="Créer un compte"]',
        # Sélecteur par texte visible imbriqué
        '//*[.//android.view.View[@content-desc="Create new account"]]',
        '//*[.//android.view.View[@content-desc="Créer un compte"]]'
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
        '//android.widget.EditText[@password="false"]/following-sibling::*//android.widget.EditText[@password="true"]',
        # Écran password-only (compte pré-rempli) : bouton "Log in" + "Forgot password?"
        '//android.widget.Button[@content-desc="Log in"]',
        '//android.widget.Button[@content-desc="Se connecter"]',
    ])

    # === Écran "mot de passe seulement" (username pré-rempli, non éditable) ===
    # Apparaît quand Instagram a déjà le compte enregistré et demande juste le mot de passe
    password_only_screen_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Forgot password?"]',
        '//android.widget.Button[@content-desc="Mot de passe oublié ?"]',
    ])
    
    # === Écran de sélection de profil (comptes enregistrés) ===
    profile_selection_screen: List[str] = field(default_factory=lambda: [
        # Boutons toujours présents sur l'écran de sélection de profil
        '//android.widget.Button[@content-desc="Use another profile"]',
        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
        '//android.widget.Button[@content-desc="Create new account"]',
        '//android.widget.Button[@content-desc="Créer un compte"]',
        '//*[contains(@text, "Use another profile")]',
        '//*[contains(@text, "Utiliser un autre profil")]',
        # L'écran a également un bouton Settings en haut à droite
        '//android.widget.Button[@content-desc="Settings" and @package="com.instagram.android"]',
    ])
    
    # === Écran de sélection de profil ===
    use_another_profile_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Use another profile"]',
        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
        '//*[contains(@text, "Use another profile")]',
        '//*[contains(@text, "Utiliser un autre profil")]'
    ])

    def saved_profile_tile_selectors(self, target_username: str, clean_username: str) -> List[str]:
        return [
            f'//android.view.ViewGroup[contains(@content-desc, "{target_username}")]',
            f'//android.view.ViewGroup[contains(@content-desc, "{clean_username}")]',
            f'//*[@text="{target_username}"]',
            f'//*[@text="{clean_username}"]',
            f'//*[contains(@content-desc, "{target_username}") and @clickable="true"]',
            f'//*[contains(@content-desc, "{clean_username}") and @clickable="true"]'
        ]

    def password_only_account_selectors(self, username: str) -> List[str]:
        return [
            f'//*[@content-desc="{username}"]',
            f'//*[contains(@content-desc, "{username}")]',
            f'//*[@text="{username}"]',
            f'//*[contains(@text, "{username}")]',
        ]

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
        # Titre sous forme de View avec content-desc (dump réel)
        '//android.view.View[@content-desc="Save your login info?"]',
        '//android.view.View[@content-desc="Enregistrer vos informations de connexion ?"]',
        '//android.view.View[contains(@content-desc, "login info")]',
        '//android.view.View[contains(@content-desc, "informations de connexion")]',
        # Fallback resource-id (versions antérieures)
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "Save")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "Enregistrer")]',
    ])
    
    save_login_info_success_popup: List[str] = field(default_factory=lambda: [
        '//android.view.View[@content-desc="Save your login info?"]',
        '//android.view.View[contains(@content-desc, "Save your login info")]',
        '//android.view.View[contains(@text, "Save your login info")]',
        '//android.view.View[contains(@content-desc, "Enregistrer vos informations")]',
        '//android.view.View[contains(@text, "Enregistrer vos informations")]'
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
        # Bouton "Save" de la popup Save Your Login Info (content-desc exact, sans resource-id)
        '//android.widget.Button[@content-desc="Save"]',
        '//android.widget.Button[@content-desc="Enregistrer"]',
        '//android.widget.Button[.//android.view.View[@content-desc="Save"]]',
        '//android.widget.Button[.//android.view.View[@content-desc="Enregistrer"]]',
    ])
    
    save_login_info_not_now_buttons: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Not now"]',
        '//android.widget.Button[@content-desc="Pas maintenant"]',
        '//android.widget.Button[.//android.view.View[@content-desc="Not now"]]',
        '//android.widget.Button[.//android.view.View[@content-desc="Pas maintenant"]]',
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
    
    # =========================================================
    # === ÉCRAN D'ACCUEIL (non connecté) ===
    # =========================================================

    # Bouton "Log into another account" sur l'écran d'accueil
    log_into_another_account_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Log into another account"]',
        '//android.widget.Button[@content-desc="Se connecter avec un autre compte"]',
        '//android.view.View[@content-desc="Log into another account"]',
        '//*[contains(@content-desc, "Log into another account")]',
        '//*[contains(@content-desc, "Se connecter avec un autre compte")]'
    ])

    # Indicateurs de l'écran d'accueil non-connecté
    home_logged_out_screen_indicators: List[str] = field(default_factory=lambda: [
        # Présence du bouton "Log into another account" (accueil avec compte WhatsApp suggéré)
        '//android.widget.Button[@content-desc="Log into another account"]',
        # Présence du lien "Create new account"
        '//android.view.View[@content-desc="Create new account"]',
        # Logo Instagram + bouton "Log into another account"
        '//android.widget.ImageView[@content-desc="Instagram from Meta"]',
    ])

    # =========================================================
    # === INSCRIPTION / CRÉATION DE COMPTE ===
    # =========================================================

    # --- Écran inscription par numéro de mobile ---
    signup_phone_screen_indicators: List[str] = field(default_factory=lambda: [
        # Titre de la page (anglais / français)
        '//android.view.View[@content-desc="What\'s your mobile number?"]',
        '//*[contains(@content-desc, "mobile number")]',
        '//*[contains(@content-desc, "numéro de mobile")]',
        # Présence du champ Mobile Number
        '//android.widget.EditText[@content-desc="Mobile Number"]',
    ])

    # --- Écran inscription par email ---
    signup_email_screen_indicators: List[str] = field(default_factory=lambda: [
        # Titre de la page (anglais / français)
        '//android.view.View[@content-desc="What\'s your email?"]',
        '//*[contains(@content-desc, "your email")]',
        '//*[contains(@content-desc, "votre e-mail")]',
        # Présence du champ Email
        '//android.widget.EditText[contains(@content-desc, "Email")]',
    ])

    # --- Champ numéro de téléphone (inscription) ---
    signup_phone_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@content-desc="Mobile Number"]',
        '//android.widget.EditText[contains(@content-desc, "Mobile")]',
        '//android.widget.EditText[contains(@content-desc, "Numéro de mobile")]',
        '(//android.widget.EditText)[1]'
    ])

    # --- Champ email (inscription) ---
    signup_email_field: List[str] = field(default_factory=lambda: [
        # Note: le content-desc contient une virgule trailing ("Email,")
        '//android.widget.EditText[contains(@content-desc, "Email")]',
        '//android.widget.EditText[contains(@content-desc, "E-mail")]',
        '(//android.widget.EditText)[1]'
    ])

    # --- Bouton "Next" (inscription) ---
    signup_next_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Next"]',
        '//android.widget.Button[@content-desc="Suivant"]',
        '//android.view.View[@content-desc="Next"]',
        '//android.view.View[@content-desc="Suivant"]',
    ])

    # --- Basculer vers inscription par email ---
    signup_switch_to_email_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Sign up with email"]',
        '//android.widget.Button[@content-desc="S\'inscrire avec un e-mail"]',
        '//android.view.View[@content-desc="Sign up with email"]',
        '//*[contains(@content-desc, "Sign up with email")]',
        '//*[contains(@content-desc, "S\'inscrire avec un e-mail")]'
    ])

    # --- Basculer vers inscription par mobile ---
    signup_switch_to_phone_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Sign up with mobile number"]',
        '//android.widget.Button[@content-desc="S\'inscrire avec un numéro de mobile"]',
        '//android.view.View[@content-desc="Sign up with mobile number"]',
        '//*[contains(@content-desc, "Sign up with mobile number")]',
        '//*[contains(@content-desc, "S\'inscrire avec un numéro de mobile")]'
    ])

    # --- "I already have an account" (retour vers login) ---
    signup_already_have_account_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="I already have an account"]',
        '//android.widget.Button[@content-desc="J\'ai déjà un compte"]',
        '//android.view.View[@content-desc="I already have an account"]',
        '//*[contains(@content-desc, "already have an account")]',
        '//*[contains(@content-desc, "déjà un compte")]'
    ])

    # =========================================================
    # === GOOGLE PASSWORD MANAGER / AUTOFILL POPUP (système Android) ===
    # =========================================================

    # Détection du popup autofill (android:id/autofill_dialog_picker)
    autofill_dataset_picker: str = '//*[@resource-id="android:id/autofill_dataset_picker"]'

    google_autofill_popup_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_dialog_picker"]',
        '//*[@resource-id="android:id/autofill_dialog_list"]',
        # Titre du popup (multilingue)
        '//*[@resource-id="com.google.android.gms:id/title"]',
    ])

    # Bouton dismiss du Google Account Picker / Autofill popup
    google_autofill_dismiss_button: List[str] = field(default_factory=lambda: [
        # Bouton X du bottom sheet "Sélectionner un compte" (com.google.android.gms)
        '//*[@resource-id="com.google.android.gms:id/cancel"]',
        '//android.widget.ImageView[@content-desc="Annuler"]',
        '//android.widget.ImageView[@content-desc="Cancel"]',
        # Bouton "Non, merci" de l'autofill dialog classique
        '//*[@resource-id="android:id/autofill_dialog_no"]',
        '//android.widget.Button[@text="Non, merci"]',
        '//android.widget.Button[@text="No, thanks"]',
    ])

    # =========================================================
    # === GOOGLE SAVE PASSWORD DIALOG (après login réussi) ===
    # =========================================================

    # "Enregistrer mot de passe dans Google ?" — apparaît après une connexion réussie
    google_save_password_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_save_title"]',
        '//*[@resource-id="com.google.android.gms:id/save_credential"]',
    ])

    # Bouton "PAS MAINTENANT" / "NOT NOW" du popup de sauvegarde de mot de passe
    google_save_password_no_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_save_no"]',
    ])

    # Bouton "ENREGISTRER" / "SAVE" du popup de sauvegarde de mot de passe
    google_save_password_yes_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_save_yes"]',
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

    # =========================================================
    # === LOGOUT (déconnexion) ===
    # =========================================================

    # Onglet Profile dans la barre de navigation
    profile_tab_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab"]',
        '//android.widget.FrameLayout[@content-desc="Profile"]',
        '//android.widget.FrameLayout[@content-desc="Profil"]',
    ])

    # Bouton "Options" (hamburger menu) en haut à droite de la page Profile
    profile_options_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@content-desc="Options"]',
        '//android.widget.ImageView[@content-desc="Settings"]',
        '//android.widget.ImageView[@content-desc="Paramètres"]',
    ])

    # Bouton "Log out" dans le menu Settings and activity (en bas, scroll requis)
    logout_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Log out"]',
        '//android.widget.Button[@text="Se déconnecter"]',
        '//android.widget.Button[@text="Log out of all accounts"]',
        '//android.widget.Button[contains(@text, "Log out")]',
        '//android.widget.Button[contains(@text, "déconnecter")]',
    ])

    # Indicateurs de la page Settings and activity
    settings_screen_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@text="Settings and activity"]',
        '//android.widget.TextView[@text="Paramètres et activité"]',
    ])

    # Bouton de confirmation du dialogue "Log out of your account?"
    logout_confirm_button: List[str] = field(default_factory=lambda: [
        # Bouton primaire dans le dialogue de confirmation (resource-id spécifique)
        '//android.widget.Button[@resource-id="com.instagram.android:id/primary_button" and @text="Log out"]',
        '//android.widget.Button[@resource-id="com.instagram.android:id/primary_button" and @text="Se déconnecter"]',
        # Fallback par texte seul
        '//android.widget.Button[@text="Log out"]',
        '//android.widget.Button[@text="Se déconnecter"]',
    ])

    # Indicateur du dialogue "Save your login info?" (apparaît juste avant la confirmation)
    save_login_info_dialog_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and @text="Save your login info?"]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "login info")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "connexion")]',
    ])

    # Bouton "Not now" dans le dialogue "Save your login info?"
    save_login_info_not_now_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@resource-id="com.instagram.android:id/negative_button" and @text="Not now"]',
        '//android.widget.Button[@resource-id="com.instagram.android:id/negative_button" and @text="Pas maintenant"]',
        '//android.widget.Button[@resource-id="com.instagram.android:id/negative_button"]',
    ])

    # Indicateur du dialogue "Log out of your account?"
    logout_confirm_dialog_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "Log out of your account")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "Déconnexion")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "déconnecter")]',
    ])

AUTH_SELECTORS = AuthSelectors()
