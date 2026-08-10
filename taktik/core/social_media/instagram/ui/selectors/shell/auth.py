from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class AuthSelectors:
    """Selectors for Instagram authentication and login."""

    # === Input fields (multilingual) ===
    _username_field_base: List[str] = field(default_factory=lambda: [
        # Generic class selector (excludes the password field to avoid false positives)
        '//android.widget.EditText[@password="false" and @clickable="true"][1]',
    ])

    @property
    def username_field(self) -> List[str]:
        return self._username_field_base + L("auth.username_field")

    # Clear button shown next to the username field when it is focused and pre-filled
    @property
    def username_clear_button(self) -> List[str]:
        return L("auth.username_clear_button")

    _password_field_base: List[str] = field(default_factory=lambda: [
        # Selector by password attribute
        '//android.widget.EditText[@password="true"]',
        # Fallback by position (second EditText)
        '(//android.widget.EditText)[2]'
    ])

    @property
    def password_field(self) -> List[str]:
        return self._password_field_base + L("auth.password_field")

    # === Boutons d'action (multilingue) ===
    _login_button_base: List[str] = field(default_factory=lambda: [
        # Generic fallback (first clickable button after the fields)
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

    # === Login page detection ===
    clickable_visible_elements: str = '//*[@clickable="true" and @visible-to-user="true"]'

    _login_screen_indicators_base: List[str] = field(default_factory=lambda: [
        # Both the username and the password fields present
        '//android.widget.EditText[@password="false"]/following-sibling::*//android.widget.EditText[@password="true"]',
    ])

    @property
    def login_screen_indicators(self) -> List[str]:
        return self._login_screen_indicators_base + L("auth.login_screen_indicators")

    # === "Password only" screen (username pre-filled, not editable) ===
    # Shown when Instagram already has the account saved and only asks for the password
    @property
    def password_only_screen_indicators(self) -> List[str]:
        return L("auth.password_only_screen_indicators")

    # === Profile picker screen (saved accounts) ===
    _profile_selection_screen_base: List[str] = field(default_factory=lambda: [
        # L'écran a également un bouton Settings en haut à droite
        '//android.widget.Button[@content-desc="Settings" and @package="com.instagram.android"]',
    ])

    @property
    def profile_selection_screen(self) -> List[str]:
        return self._profile_selection_screen_base + L("auth.profile_selection_screen")

    # === Profile picker screen ===
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

    # === Generic popup buttons ===
    @property
    def save_button_selectors(self) -> List[str]:
        # "Save" button of the Save Your Login Info popup (exact content-desc, no resource-id)
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

    # "Log into another account" button on the welcome screen
    @property
    def log_into_another_account_button(self) -> List[str]:
        return L("auth.log_into_another_account_button")

    # Indicateurs de l'écran d'accueil non-connecté
    @property
    def home_logged_out_screen_indicators(self) -> List[str]:
        return L("auth.home_logged_out_screen_indicators")

    # =========================================================
    # === SIGNUP / ACCOUNT CREATION ===
    # =========================================================

    # --- Signup by mobile number screen ---
    signup_phone_screen_indicators: List[str] = field(default_factory=lambda: [
        # Page title (English / French)
        '//android.view.View[@content-desc="What\'s your mobile number?"]',
        '//*[contains(@content-desc, "mobile number")]',
        '//*[contains(@content-desc, "numéro de mobile")]',
        # Mobile Number field present
        '//android.widget.EditText[@content-desc="Mobile Number"]',
    ])

    # --- Signup by email screen ---
    signup_email_screen_indicators: List[str] = field(default_factory=lambda: [
        # Page title (English / French)
        '//android.view.View[@content-desc="What\'s your email?"]',
        '//*[contains(@content-desc, "your email")]',
        '//*[contains(@content-desc, "votre e-mail")]',
        # Email field present
        '//android.widget.EditText[contains(@content-desc, "Email")]',
    ])

    # --- Phone number field (signup) ---
    signup_phone_field: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@content-desc="Mobile Number"]',
        '//android.widget.EditText[contains(@content-desc, "Mobile")]',
        '//android.widget.EditText[contains(@content-desc, "Numéro de mobile")]',
        '(//android.widget.EditText)[1]'
    ])

    # --- Email field (signup) ---
    signup_email_field: List[str] = field(default_factory=lambda: [
        # Note: the content-desc carries a trailing comma ("Email,")
        '//android.widget.EditText[contains(@content-desc, "Email")]',
        '//android.widget.EditText[contains(@content-desc, "E-mail")]',
        '(//android.widget.EditText)[1]'
    ])

    # --- "Next" button (signup) ---
    @property
    def signup_next_button(self) -> List[str]:
        return L("auth.signup_next_button")

    # --- Switch to signing up by email ---
    signup_switch_to_email_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Sign up with email"]',
        '//android.widget.Button[@content-desc="S\'inscrire avec un e-mail"]',
        '//android.view.View[@content-desc="Sign up with email"]',
        '//*[contains(@content-desc, "Sign up with email")]',
        '//*[contains(@content-desc, "S\'inscrire avec un e-mail")]'
    ])

    # --- Switch to signing up by mobile ---
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

    # Autofill popup detection (android:id/autofill_dialog_picker)
    autofill_dataset_picker: str = '//*[@resource-id="android:id/autofill_dataset_picker"]'

    google_autofill_popup_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_dialog_picker"]',
        '//*[@resource-id="android:id/autofill_dialog_list"]',
        # Popup title (multilingual)
        '//*[@resource-id="com.google.android.gms:id/title"]',
    ])

    # Dismiss button of the Google account picker / autofill popup
    _google_autofill_dismiss_button_base: List[str] = field(default_factory=lambda: [
        # Close button of the account-selection bottom sheet (com.google.android.gms)
        '//*[@resource-id="com.google.android.gms:id/cancel"]',
        # "No thanks" button of the classic autofill dialog
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

    # "Save password to Google?" — shown after a successful login
    google_save_password_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_save_title"]',
        '//*[@resource-id="com.google.android.gms:id/save_credential"]',
    ])

    # "NOT NOW" button of the password-saving popup
    google_save_password_no_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="android:id/autofill_save_no"]',
    ])

    # "SAVE" button of the password-saving popup
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

    # Profile tab in the navigation bar
    _profile_tab_button_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/profile_tab"]',
    ])

    @property
    def profile_tab_button(self) -> List[str]:
        return self._profile_tab_button_base + L("auth.profile_tab_button")

    # "Options" button (hamburger menu) at the top right of the profile page
    profile_options_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[@content-desc="Options"]',
        '//android.widget.ImageView[@content-desc="Settings"]',
        '//android.widget.ImageView[@content-desc="Paramètres"]',
    ])

    # "Log out" button in the settings menu (at the bottom, scrolling required)
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

    # Confirmation button of the "Log out of your account?" dialog
    logout_confirm_button: List[str] = field(default_factory=lambda: [
        # Primary button of the confirmation dialog (specific resource-id)
        '//android.widget.Button[@resource-id="com.instagram.android:id/primary_button" and @text="Log out"]',
        '//android.widget.Button[@resource-id="com.instagram.android:id/primary_button" and @text="Se déconnecter"]',
        # Text-only fallback
        '//android.widget.Button[@text="Log out"]',
        '//android.widget.Button[@text="Se déconnecter"]',
    ])

    # Marker of the "Save your login info?" dialog (shown just before the confirmation)
    _save_login_info_dialog_indicators_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "login info")]',
        '//android.widget.TextView[@resource-id="com.instagram.android:id/igds_headline_headline" and contains(@text, "connexion")]',
    ])

    @property
    def save_login_info_dialog_indicators(self) -> List[str]:
        return self._save_login_info_dialog_indicators_base + L("auth.save_login_info_dialog_indicators")

    # "Not now" button of the "Save your login info?" dialog
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
    # === SWITCH ACCOUNT (several accounts logged in on the device) ===
    # =========================================================
    # Flow: profile -> settings menu -> log out -> logged-out account picker -> tap the
    # target account row. The button labels are language-dependent (bilingual inline, like
    # logout_button / settings_screen_indicators); the account ROWS are identified by the
    # username in content-desc, so they are language-neutral.

    # Opens the account sheet WITHOUT logging out: the @username (+ chevron) at the top of
    # the profile page. Tapping it opens the sheet of logged-in accounts.
    profile_username_switcher_button: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/action_bar_username_container"]',
        '//android.widget.LinearLayout[.//*[@resource-id="com.instagram.android:id/action_bar_title_chevron"]]',
        '//*[@resource-id="com.instagram.android:id/action_bar_title" and @clickable="true"]',
    ])

    # Markers of the logged-out account picker: the "use another profile" button is
    # present.
    account_picker_indicators: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Use another profile"]',
        '//android.widget.Button[@content-desc="Utiliser un autre profil"]',
        '//android.widget.Button[contains(@content-desc, "another profile")]',
        '//android.widget.Button[contains(@content-desc, "autre profil")]',
    ])

    # Indicateurs du fil d'accueil IG (connecte). Sert a detecter l'auto-switch : apres un logout,
    # Instagram may land on another logged-in account HOME instead of showing the picker.
    home_feed_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/feed_timeline"]',
        '//*[@resource-id="com.instagram.android:id/feed_tab"]',
        '//*[@resource-id="com.instagram.android:id/reels_tray_container"]',
    ])

    # Account-row candidates (picker + menu): a clickable ViewGroup whose content-desc IS
    # the username, sometimes followed by a notifications suffix. No resource-id, so the
    # candidates are enumerated, the non-account labels below are filtered out, and the
    # username is derived from the content-desc.
    account_row_candidates: List[str] = field(default_factory=lambda: [
        '//android.view.ViewGroup[@clickable="true"]',
    ])

    # Labels to EXCLUDE from the account enumeration (picker/menu buttons, multilingual).
    account_row_exclude_labels: List[str] = field(default_factory=lambda: [
        'Use another profile', 'Utiliser un autre profil',
        'Create account', 'Créer un compte', 'Create new account', 'Créer un nouveau compte',
        'Add account', 'Ajouter un compte',
        'Settings', 'Paramètres', 'Options', 'Back', 'Retour',
        'Home', 'Accueil', 'Log out', 'Se déconnecter',
        # Home-feed bottom navigation tabs — never accounts.
        'Reels', 'Message', 'Messages', 'Profile', 'Profil', 'Notifications',
        'Search and explore', 'Recherche et exploration', 'Rechercher',
    ])

AUTH_SELECTORS = AuthSelectors()
