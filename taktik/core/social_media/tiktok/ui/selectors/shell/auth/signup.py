"""Selectors for the TikTok signup flow."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L

# ---------------------------------------------------------------------------
# Signup selectors
# ---------------------------------------------------------------------------

@dataclass
class SignupSelectors:
    """Selectors for the TikTok signup flow.

    Flow observé :
      1. saved-account screen -> tap the signup link at the bottom
      2. Date de naissance      → roues jour/mois/année → "Continuer"
      3. method choice -> use a phone number or an email address
                                  (ou Facebook / Google)
      4. Saisie téléphone/email → onglets "Téléphone" / "E-mail" → "Continuer"
      5. (to be completed with further dumps)
    """

    # -- Welcome screen (saved account) --------------------------------

    # Signup button at the bottom of the page
    # resource-id: com.zhiliaoapp.musically:id/mwu
    _signup_link_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/mwu")]',
    ])

    @property
    def signup_link(self) -> List[str]:
        return self._signup_link_base + L("signup.signup_link")

    # ── Indicateur popup "Inscription à TikTok" ────────────────────────────

    # Title of the signup popup, per package variant
    # "Sign up for TikTok" (EN). Apparaît juste après la birthday gate.
    # resource-id: com.zhiliaoapp.musically:id/title
    # NOTE: removed the generic contains(@text, "TikTok") selector — too broad,
    # it matched the birthday screen title on some Samsung devices.
    # Compose-based UI: title has no resource-id — match by full precise text
    @property
    def signup_popup_indicator(self) -> List[str]:
        return L("signup.signup_popup_indicator")

    # -- Signup link on the birthday gate ------------------------------

    # On the pre-signup birthday gate, a button at the bottom invites to sign
    # up. It is what tells that gate apart from the birthday screen of the
    # signup flow itself.
    #
    # resource-id: com.zhiliaoapp.musically:id/mfb
    _birthday_gate_inscription_link_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/mfb")]',
        # Generic fallbacks — safe because signup_popup_indicator (whose title
        # TextView also mentions "Inscription") is checked first in _detect_screen().
        # Also cover cases where the element is a TextView or generic View
        '//*[@clickable="true" and (contains(@text, "inscrire") or contains(@content-desc, "inscrire"))]',
    ])

    @property
    def birthday_gate_inscription_link(self) -> List[str]:
        return self._birthday_gate_inscription_link_base + L("signup.birthday_gate_inscription_link")

    # ── Écran date de naissance ────────────────────────────────────────────

    # Indicateur de l'écran date de naissance
    # resource-id musically: com.zhiliaoapp.musically:id/aby
    # resource-id trill:     com.ss.android.ugc.trill:id/aac  (patché → id/aac)
    _birthday_screen_indicator_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/aby")]',
        '//android.widget.TextView[contains(@resource-id, ":id/aac")]',
        # Fallback: the birthday picker always has ≥3 scrollable SeekBars
        # (day / month / year wheels). Video scrubbers only have 1, so [3]
        # ensures this only matches a true birthday picker screen.
        '//android.widget.SeekBar[@scrollable="true"][3]',
    ])

    @property
    def birthday_screen_indicator(self) -> List[str]:
        return self._birthday_screen_indicator_base + L("signup.birthday_screen_indicator")

    # Date-of-birth field, showing the selected date live
    # resource-id musically: com.zhiliaoapp.musically:id/kcl
    # resource-id trill:     com.ss.android.ugc.trill:id/jsh  (patché → id/jsh)
    # Valeurs possibles : "10 juin 2025" / "10 June 2025" / placeholder hint
    _birthday_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@resource-id, ":id/kcl")]',
        '//android.widget.EditText[contains(@resource-id, ":id/jsh")]',
        '(//android.widget.EditText)[1]',
    ])

    @property
    def birthday_input(self) -> List[str]:
        return self._birthday_input_base + L("signup.birthday_input")

    # SeekBar (roue déroulante) – jour
    # Day picker
    # resource-id trill:     com.ss.android.ugc.trill:id/erv  (patché → id/erv)
    _birthday_day_picker_base: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/f53")]',
        '//android.widget.SeekBar[contains(@resource-id, ":id/erv")]',
        '(//android.widget.SeekBar[@scrollable="true"])[1]',
    ])

    @property
    def birthday_day_picker(self) -> List[str]:
        return self._birthday_day_picker_base + L("signup.birthday_day_picker")

    # SeekBar – mois
    # Month picker
    # resource-id trill:     com.ss.android.ugc.trill:id/n7o  (patché → id/n7o)
    _birthday_month_picker_base: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/o18")]',
        '//android.widget.SeekBar[contains(@resource-id, ":id/n7o")]',
        '(//android.widget.SeekBar[@scrollable="true"])[2]',
    ])

    @property
    def birthday_month_picker(self) -> List[str]:
        return self._birthday_month_picker_base + L("signup.birthday_month_picker")

    # SeekBar – année
    # Year picker
    _birthday_year_picker_base: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/year_picker")]',
        '(//android.widget.SeekBar[@scrollable="true"])[3]',
    ])

    @property
    def birthday_year_picker(self) -> List[str]:
        return self._birthday_year_picker_base + L("signup.birthday_year_picker")

    # Continue button on the date-of-birth screen
    # resource-id musically: com.zhiliaoapp.musically:id/ac8
    # resource-id trill:     com.ss.android.ugc.trill:id/aal  (patché → id/aal)
    _birthday_continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/ac8")]',
        '//android.widget.Button[contains(@resource-id, ":id/aal")]',
    ])

    @property
    def birthday_continue_button(self) -> List[str]:
        return self._birthday_continue_button_base + L("signup.birthday_continue_button")

    # -- Signup method choice screen -----------------------------------

    # Button offering to use a phone number or an email address
    # On the signup popup
    # resource-id: com.zhiliaoapp.musically:id/e52
    _use_phone_or_email_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/e52") and contains(@content-desc, "téléphone")]',
        '//android.widget.Button[contains(@resource-id, ":id/e52") and contains(@content-desc, "phone")]',
        '//*[contains(@content-desc, "numéro de téléphone") and contains(@content-desc, "e-mail")]',
        '//*[contains(@content-desc, "phone") and contains(@content-desc, "email")]',
        # Compose button: clickable parent has no content-desc; child TextView has the text
        '//*[@clickable="true" and ./android.widget.TextView[contains(@text, "phone") and contains(@text, "email")]]',
        '//*[contains(@text, "numéro de téléphone") and contains(@text, "e-mail")]',
    ])

    @property
    def use_phone_or_email_button(self) -> List[str]:
        return self._use_phone_or_email_button_base + L("signup.use_phone_or_email_button")

    # ── Écran saisie téléphone / email (onglets) ───────────────────────────

    # Indicateur de l'écran inscription (titre)
    # resource-id: com.zhiliaoapp.musically:id/ohi  text="Inscription"
    _register_screen_indicator_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/ohi")]',
    ])

    @property
    def register_screen_indicator(self) -> List[str]:
        return self._register_screen_indicator_base + L("signup.register_screen_indicator")

    # Phone tab, marked selected when active
    @property
    def tab_phone(self) -> List[str]:
        return L("signup.tab_phone")

    # Onglet "E-mail"
    @property
    def tab_email(self) -> List[str]:
        return L("signup.tab_email")

    # Country-code picker inside the phone tab
    # resource-id: com.zhiliaoapp.musically:id/ps9  (LinearLayout cliquable)
    country_code_selector: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[contains(@resource-id, ":id/ps9") and @clickable="true"]',
        '//*[.//android.widget.TextView[contains(@resource-id, ":id/eqh")]]',
    ])

    # Phone number field, identified by its hint, with no resource-id
    _phone_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "téléphone")]',
        '//android.widget.EditText[contains(@hint, "phone")]',
    ])

    @property
    def phone_input(self) -> List[str]:
        return self._phone_input_base + L("signup.phone_input")

    # Email field, identified by its hint, with no resource-id
    _email_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "e-mail")]',
        '//android.widget.EditText[contains(@hint, "email")]',
    ])

    @property
    def email_input(self) -> List[str]:
        return self._email_input_base + L("signup.email_input")

    # Continue button on the phone/email screen
    # Shared by both tabs
    _continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/ezo")]',
    ])

    @property
    def continue_button(self) -> List[str]:
        return self._continue_button_base + L("signup.continue_button")

    # Case à cocher "Enregistre tes informations de connexion" (onglet Téléphone)
    # resource-id: com.zhiliaoapp.musically:id/oyk
    save_login_checkbox: List[str] = field(default_factory=lambda: [
        '//android.widget.CheckBox[contains(@resource-id, ":id/oyk")]',
    ])

    # Case à cocher marketing (onglet E-mail)
    # resource-id: com.zhiliaoapp.musically:id/gk8
    marketing_checkbox: List[str] = field(default_factory=lambda: [
        '//android.widget.CheckBox[contains(@resource-id, ":id/gk8")]',
    ])

    # -- Back button, shared across the signup screens -----------------
    @property
    def back_button(self) -> List[str]:
        return L("signup.back_button")

    # -- Verification code screen --------------------------------------
    # This screen appears after the email or phone has been entered.
    # A six-digit code is sent and an input field is shown.
    # Note: the exact resource-ids remain to be confirmed from a dump.

    # Indicateur de l'écran OTP (titre ou message mentionnant "code")
    # Titles actually observed on that screen
    # The resend entry is always present there
    _otp_screen_indicator_base: List[str] = field(default_factory=lambda: [
        # Fallback: six single-character fields form the code grid
        '//android.widget.EditText[string-length(@hint)=1]',
    ])

    @property
    def otp_screen_indicator(self) -> List[str]:
        return self._otp_screen_indicator_base + L("signup.otp_screen_indicator")

    # The code input may be a single field or the first cell of a
    # six-cell grid
    otp_input: List[str] = field(default_factory=lambda: [
        # Single six-digit field
        '//android.widget.EditText[contains(@hint, "code") or contains(@hint, "Code")]',
        # Première case individuelle (grille 6×1)
        '(//android.widget.EditText[@hint="" or string-length(@hint)<=1])[1]',
        # Fallback : premier EditText de l'écran
        '(//android.widget.EditText)[1]',
    ])

    # Resend button, to trigger a new code when needed
    @property
    def otp_resend_button(self) -> List[str]:
        return L("signup.otp_resend_button")

    # Continue button after the code is entered
    _otp_continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, "ezo")]',
    ])

    @property
    def otp_continue_button(self) -> List[str]:
        return self._otp_continue_button_base + L("signup.otp_continue_button")

    # -- Password creation screen --------------------------------------
    # Dump observé : ui_dump_20260504_021827.xml
    # Titre   : id=e_c  text="Créer un mot de passe" / "Create a password"
    # Input:  field identified by its hint
    # Toggle: reveal button
    # Rule:   unmet-requirements marker
    # Skip    : Button text="Ignorer" / "Skip"
    # Valider : id=emm Button text="Continuer" / "Continue"
    #
    # Règles TikTok : 8–20 chars, ≥1 lettre, ≥1 chiffre, ≥1 spécial (#?!@)

    _password_entry_indicator_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/e_c") and contains(@text, "password")]',
        # Requirement indicator is unique to this screen
        '//android.widget.ImageView[contains(@resource-id, ":id/d6h")]',
    ])

    @property
    def password_entry_indicator(self) -> List[str]:
        return self._password_entry_indicator_base + L("signup.password_entry_indicator")

    _password_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "password")]',
    ])

    @property
    def password_input(self) -> List[str]:
        return self._password_input_base + L("signup.password_input")

    _password_continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/emm")]',
    ])

    @property
    def password_continue_button(self) -> List[str]:
        return self._password_continue_button_base + L("signup.password_continue_button")

    @property
    def password_skip_button(self) -> List[str]:
        return L("signup.password_skip_button")

    # -- Username creation screen --------------------------------------
    # Dump observé : ui_dump_20260504_021944.xml
    # Titre   : id=e_c  text="Créer un surnom" / "Create a username"
    # Subtitle: optional description, editable later
    # Input   : EditText hint="Ajoute ton surnom" / "Add your username"
    # Compteur: id=fuh  text="0/30"
    # Skip    : Button text="Ignorer" / "Skip"
    # Valider : id=emm Button text="Continuer" / "Continue"

    _nickname_entry_indicator_base: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/e_c") and contains(@text, "username")]',
        # Counter "0/30" is unique to this screen
        '//android.widget.TextView[contains(@resource-id, ":id/fuh")]',
    ])

    @property
    def nickname_entry_indicator(self) -> List[str]:
        return self._nickname_entry_indicator_base + L("signup.nickname_entry_indicator")

    _nickname_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "username")]',
    ])

    @property
    def nickname_input(self) -> List[str]:
        return self._nickname_input_base + L("signup.nickname_input")

    _nickname_continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/emm")]',
    ])

    @property
    def nickname_continue_button(self) -> List[str]:
        return self._nickname_continue_button_base + L("signup.nickname_continue_button")

    @property
    def nickname_skip_button(self) -> List[str]:
        return L("signup.nickname_skip_button")

    # ── Popup GDPR / politique de données ──────────────────────────────────
    # Dump observé : ui_dump_20260504_022753.xml
    # Titre   : id=w4m  text="Remote-access "transfers of EEA User Data to China"…"
    # Body:   explanatory text, scrollable
    # Button: acknowledgement, with no resource-id
    #
    # This popup can appear at any point of the signup flow, layered directly
    # over whatever screen is showing.

    gdpr_popup_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/w4m")]',
        '//android.widget.Button[@text="Got it"]',
    ])

    gdpr_got_it_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Got it"]',
        '//android.widget.Button[contains(@text, "Got it")]',
        '//android.widget.Button[@text="J\'ai compris"]',
        '//android.widget.Button[contains(@text, "J\'ai compris")]',
    ])


SIGNUP_SELECTORS = SignupSelectors()
