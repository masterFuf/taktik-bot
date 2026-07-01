from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class AuthSelectors:
    """Sélecteurs pour l'authentification et le login Instagram."""

    # === Champs de saisie (multilingue) ===
    _username_field_base: List[str] = field(default_factory=lambda: [
        # Sélecteur générique par classe (exclut le champ password pour éviter faux positifs)
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
    ])

    @property
    def username_field(self) -> List[str]:
        return self._username_field_base + L("auth.username_field")

    # Bouton X/effacer qui apparaît à côté du champ username quand il est focalisé et pré-rempli
    @property
    def username_clear_button(self) -> List[str]:
        return L("auth.username_clear_button")

    _password_field_base: List[str] = field(default_factory=lambda: [
        # Sélecteur par attribut password
        '//android.widget.EditText[@password="true"]',
        # Fallback par position (second EditText)
        '(//android.widget.EditText)[2]'
    ])

    @property
    def password_field(self) -> List[str]:
        return self._password_field_base + L("auth.password_field")

    # === Boutons d'action (multilingue) ===
    _login_button_base: List[str] = field(default_factory=lambda: [
        # Fallback générique (premier bouton cliquable après les champs)
        '(//android.widget.Button[@clickable="true"])[1]'
    ])

    @property
    def login_button(self) -> List[str]:
        return self._login_button_base + L("auth.login_button")

    @property
    def create_account_button(self) -> List[str]:
        return L("auth.create_account_button")

    @property
    def forgot_password_button(self) -> List[str]:
        return L("auth.forgot_password_button")

    # === Détection de la page de login ===
    clickable_visible_elements: str = '//*[@clickable="true" and @visible-to-user="true"]'

    _login_screen_indicators_base: List[str] = field(default_factory=lambda: [
        # Présence simultanée des champs username et password
        '//android.widget.EditText[@password="false"]/following-sibling::*//android.widget.EditText[@password="true"]',
    ])

    @property
    def login_screen_indicators(self) -> List[str]:
        return self._login_screen_indicators_base + L("auth.login_screen_indicators")

    # === Écran "mot de passe seulement" (username pré-rempli, non éditable) ===
    # Apparaît quand Instagram a déjà le compte enregistré et demande juste le mot de passe
    @property
    def password_only_screen_indicators(self) -> List[str]:
        return L("auth.password_only_screen_indicators")

    # === Écran de sélection de profil (comptes enregistrés) ===
    _profile_selection_screen_base: List[str] = field(default_factory=lambda: [
        # L'écran a également un bouton Settings en haut à droite
        '//android.widget.Button[@content-desc="Settings" and @package="com.instagram.android"]',
    ])

    @property
    def profile_selection_screen(self) -> List[str]:
        return self._profile_selection_screen_base + L("auth.profile_selection_screen")

    # === Écran de sélection de profil ===
    @property
    def use_another_profile_button(self) -> List[str]:
        return L("auth.use_another_profile_button")

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
    @property
    def error_message_selectors(self) -> List[str]:
        return L("auth.error_message_selectors")

    # === 2FA et vérification ===
    _two_factor_indicators_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "code")]'
    ])

    @property
    def two_factor_indicators(self) -> List[str]:
        return self._two_factor_indicators_base + L("auth.two_factor_indicators")

    two_factor_code_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "code")]',
        '//android.widget.EditText[contains(@hint, "Code")]',
        '(//android.widget.EditText)[1]'
    ])

    @property
    def two_factor_confirm_button(self) -> List[str]:
        return L("auth.two_factor_confirm_button")

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
    _save_login_info_popup_base: List[str] = field(default_factory=lambda: [
        '//android.view.View[contains(@content-desc, "login info")]',
        '//android.view.View[contains(@content-desc, "informations de connexion")]',
    ])

    @property
    def save_login_info_popup(self) -> List[str]:
        return self._save_login_info_popup_base + L("auth.save_login_info_popup")

    @property
    def save_login_info_success_popup(self) -> List[str]:
        return L("auth.save_login_info_success_popup")

    _notification_popup_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "Turn on Notifications")]',
        '//android.widget.TextView[contains(@text, "Activer les notifications")]',
        '//android.widget.Button[contains(@text, "Turn On")]',
        '//android.widget.Button[contains(@text, "Activer")]',
    ])

    @property
    def notification_popup(self) -> List[str]:
        return self._notification_popup_base + L("auth.notification_popup")

    # === Popup contacts (Find friends) ===
    _contacts_sync_popup_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Autorisez l\'accès à vos contacts")]',
        '//*[contains(@text, "Find friends")]',
        '//*[contains(@text, "Trouver des amis")]',
        '//android.widget.Button[@content-desc="Ignorer"]',
        '//android.widget.Button[@content-desc="Skip"]',
    ])

    @property
    def contacts_sync_popup(self) -> List[str]:
        return self._contacts_sync_popup_base + L("auth.contacts_sync_popup")

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
    _location_permission_dialog_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Permettre à Instagram d\'accéder à la position")]',
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_allow_button"]',
        '//android.widget.Button[@resource-id="com.android.packageinstaller:id/permission_deny_button"]',
        '//android.widget.Button[@text="AUTORISER"]',
        '//android.widget.Button[@text="ALLOW"]',
        '//android.widget.Button[@text="REFUSER"]',
        '//android.widget.Button[@text="DENY"]'
    ])

    @property
    def location_permission_dialog(self) -> List[str]:
        return self._location_permission_dialog_base + L("auth.location_permission_dialog")

    # === Boutons génériques pour popups ===
    @property
    def save_button_selectors(self) -> List[str]:
        # Bouton "Save" de la popup Save Your Login Info (content-desc exact, sans resource-id)
        return L("auth.save_button_selectors")

    _save_login_info_not_now_buttons_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Not now"]',
        '//android.widget.Button[.//android.view.View[@content-desc="Not now"]]',
    ])

    @property
    def save_login_info_not_now_buttons(self) -> List[str]:
        return self._save_login_info_not_now_buttons_base + L("auth.save_login_info_not_now_buttons")

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
    @property
    def log_into_another_account_button(self) -> List[str]:
        return L("auth.log_into_another_account_button")

    # Indicateurs de l'écran d'accueil non-connecté
    @property
    def home_logged_out_screen_indicators(self) -> List[str]:
        return L("auth.home_logged_out_screen_indicators")

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
    @property
    def signup_next_button(self) -> List[str]:
        return L("auth.signup_next_button")

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
    _google_autofill_dismiss_button_base: List[str] = field(default_factory=lambda: [
        # Bouton X du bottom sheet "Sélectionner un compte" (com.google.android.gms)
        '//*[@resource-id="com.google.android.gms:id/cancel"]',
        # Bouton "Non, merci" de l'autofill dialog classique
        '//*[@resource-id="android:id/autofill_dialog_no"]',
        '//android.widget.Button[@text="Non, merci"]',
        '//android.widget.Button[@text="No, thanks"]',
    ])

    @property
    def google_autofill_dismiss_button(self) -> List[str]:
        return self._google_autofill_dismiss_button_base + L("auth.google_autofill_dismiss_button")

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
    _profile_tab_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab"]',
    ])

    @property
    def profile_tab_button(self) -> List[str]:
        return self._profile_tab_button_base + L("auth.profile_tab_button")

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
    _save_login_info_dialog_indicators_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "login info")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "connexion")]',
    ])

    @property
    def save_login_info_dialog_indicators(self) -> List[str]:
        return self._save_login_info_dialog_indicators_base + L("auth.save_login_info_dialog_indicators")

    # Bouton "Not now" dans le dialogue "Save your login info?"
    _save_login_info_not_now_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@resource-id="com.instagram.android:id/negative_button" and @text="Not now"]',
        '//android.widget.Button[@resource-id="com.instagram.android:id/negative_button"]',
    ])

    @property
    def save_login_info_not_now_button(self) -> List[str]:
        return self._save_login_info_not_now_button_base + L("auth.save_login_info_not_now_button")

    # Indicateur du dialogue "Log out of your account?"
    logout_confirm_dialog_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "Log out of your account")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "Déconnexion")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "déconnecter")]',
    ])

    # =========================================================
    # === SWITCH ACCOUNT (plusieurs comptes connectes sur le device) ===
    # =========================================================
    # Flow (dumps 2026-07-01) : profil -> menu Settings -> Log out -> ecran "picker" des comptes
    # connectes (logged-out) -> taper la ligne du compte cible. Les libelles boutons sont
    # langue-dependants (bilingue inline, comme logout_button / settings_screen_indicators) ; les
    # LIGNES de compte sont identifiees par le username (content-desc), donc langue-neutres.

    # Bouton d'ouverture du selecteur de comptes SANS logout : le @username (+ chevron) en haut
    # de la page Profile. Le taper ouvre la feuille des comptes connectes (dump profil 2026-07-01).
    profile_username_switcher_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]',
        '//android.widget.LinearLayout[.//*[@resource-id="com.instagram.android:id/action_bar_title_chevron"]]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title" and @clickable="true"]',
    ])

    # Indicateurs de l'ecran "picker" de comptes (logged-out, apres logout) : bouton
    # "Use another profile" / "Utiliser un autre profil" present.
    account_picker_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Use another profile"]',
        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
        '//android.widget.Button[contains(@content-desc, "another profile")]',
        '//android.widget.Button[contains(@content-desc, "autre profil")]',
    ])

    # Indicateurs du fil d'accueil IG (connecte). Sert a detecter l'auto-switch : apres un logout,
    # IG peut basculer sur le HOME d'un autre compte connecte au lieu d'afficher le picker.
    home_feed_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/feed_timeline"]',
        '//*[@resource-id="com.instagram.android:id/feed_tab"]',
        '//*[@resource-id="com.instagram.android:id/reels_tray_container"]',
    ])

    # Candidats "ligne de compte" (picker + menu) : ViewGroup cliquable dont le content-desc EST le
    # username (parfois suivi de ",  New notifications" / ", Nouvelles notifications"). Pas de
    # resource-id -> on enumere les candidats puis on filtre les libelles non-comptes (ci-dessous)
    # et on derive le username = content-desc.split(",")[0].
    account_row_candidates: List[str] = field(default_factory=lambda: [
        '//android.view.ViewGroup[@clickable="true"]',
    ])

    # Libelles a EXCLURE de l'enumeration des comptes (boutons du picker/menu, multilingue).
    account_row_exclude_labels: List[str] = field(default_factory=lambda: [
        'Use another profile', 'Utiliser un autre profil',
        'Create account', 'Créer un compte', 'Create new account', 'Créer un nouveau compte',
        'Add account', 'Ajouter un compte',
        'Settings', 'Paramètres', 'Options', 'Back', 'Retour',
        'Home', 'Accueil', 'Log out', 'Se déconnecter',
    ])

AUTH_SELECTORS = AuthSelectors()
