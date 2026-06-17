"""Selectors for the TikTok signup flow."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L

# ---------------------------------------------------------------------------
# Sélecteurs pour l'inscription (signup / register)
# ---------------------------------------------------------------------------

@dataclass
class SignupSelectors:
    """Sélecteurs pour le flow d'inscription TikTok.

    Flow observé :
      1. Écran compte existant  → clic "Inscription" (lien bas de page)
      2. Date de naissance      → roues jour/mois/année → "Continuer"
      3. Choix méthode          → "Utiliser un numéro de téléphone ou une adresse e-mail"
                                  (ou Facebook / Google)
      4. Saisie téléphone/email → onglets "Téléphone" / "E-mail" → "Continuer"
      5. (suite à compléter avec les prochains dumps)
    """

    # ── Écran d'accueil (compte existant sauvegardé) ──────────────────────

    # Bouton "Tu n'as pas de compte ? Inscription" (bas de page)
    # resource-id: com.zhiliaoapp.musically:id/mwu
    _signup_link_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/mwu")]',
    ])

    @property
    def signup_link(self) -> List[str]:
        return self._signup_link_base + L("signup.signup_link")

    # ── Indicateur popup "Inscription à TikTok" ────────────────────────────

    # Titre de la popup d'inscription : id=title text="Inscription à TikTok" (trill) /
    # "Sign up for TikTok" (EN). Apparaît juste après la birthday gate.
    # resource-id: com.zhiliaoapp.musically:id/title
    # NOTE: removed the generic contains(@text, "TikTok") selector — too broad,
    # it matched the birthday screen title on some Samsung devices.
    # Compose-based UI: title has no resource-id — match by full precise text
    @property
    def signup_popup_indicator(self) -> List[str]:
        return L("signup.signup_popup_indicator")

    # ── Lien "Inscription" sur la birthday gate ────────────────────────────

    # Sur la page birthday gate (pré-inscription), un bouton en bas invite
    # à s'inscrire : id=mfb text="Plus de fonctionnalités intéressantes ? Inscription"
    # (FR) / "More fun features? Sign up" (EN). Permet de distinguer cette
    # birthday gate de la birthday screen dans le flow d'inscription.
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

    # Champ texte "Date de naissance" — affiche la date sélectionnée en temps réel
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
    # resource-id musically: com.zhiliaoapp.musically:id/f53  content-desc: "Sélecteur du jour"
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
    # resource-id musically: com.zhiliaoapp.musically:id/o18  content-desc: "Sélecteur du mois"
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
    # resource-id: com.zhiliaoapp.musically:id/year_picker  content-desc: "Sélecteur de l'année"
    _birthday_year_picker_base: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/year_picker")]',
        '(//android.widget.SeekBar[@scrollable="true"])[3]',
    ])

    @property
    def birthday_year_picker(self) -> List[str]:
        return self._birthday_year_picker_base + L("signup.birthday_year_picker")

    # Bouton "Continuer" sur l'écran date de naissance
    # resource-id musically: com.zhiliaoapp.musically:id/ac8
    # resource-id trill:     com.ss.android.ugc.trill:id/aal  (patché → id/aal)
    _birthday_continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/ac8")]',
        '//android.widget.Button[contains(@resource-id, ":id/aal")]',
    ])

    @property
    def birthday_continue_button(self) -> List[str]:
        return self._birthday_continue_button_base + L("signup.birthday_continue_button")

    # ── Écran choix de la méthode d'inscription ────────────────────────────

    # Bouton "Utiliser un numéro de téléphone ou une adresse e-mail"
    # Sur la popup signup : id=e52, content-desc="Utiliser un numéro de téléphone ou une adresse e-mail"
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

    # Onglet "Téléphone"  (content-desc="Téléphone", selected quand actif)
    @property
    def tab_phone(self) -> List[str]:
        return L("signup.tab_phone")

    # Onglet "E-mail"
    @property
    def tab_email(self) -> List[str]:
        return L("signup.tab_email")

    # Sélecteur du code pays (bouton "US +1" dans l'onglet Téléphone)
    # resource-id: com.zhiliaoapp.musically:id/ps9  (LinearLayout cliquable)
    country_code_selector: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[contains(@resource-id, ":id/ps9") and @clickable="true"]',
        '//*[.//android.widget.TextView[contains(@resource-id, ":id/eqh")]]',
    ])

    # Champ numéro de téléphone (hint="Numéro de téléphone", pas de resource-id)
    _phone_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "téléphone")]',
        '//android.widget.EditText[contains(@hint, "phone")]',
    ])

    @property
    def phone_input(self) -> List[str]:
        return self._phone_input_base + L("signup.phone_input")

    # Champ adresse e-mail (hint="Adresse e-mail", pas de resource-id)
    _email_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@hint, "e-mail")]',
        '//android.widget.EditText[contains(@hint, "email")]',
    ])

    @property
    def email_input(self) -> List[str]:
        return self._email_input_base + L("signup.email_input")

    # Bouton "Continuer" sur l'écran téléphone/email
    # resource-id: com.zhiliaoapp.musically:id/ezo  (commun aux deux onglets)
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

    # ── Bouton retour (partagé entre les écrans d'inscription) ─────────────
    @property
    def back_button(self) -> List[str]:
        return L("signup.back_button")

    # ── Écran saisie du code de vérification (OTP) ─────────────────────────
    # Cet écran apparaît après la saisie de l'email ou du téléphone.
    # TikTok envoie un code à 6 chiffres et affiche un champ de saisie.
    # Note : les resource-id exacts seront confirmés avec un dump de cet écran.

    # Indicateur de l'écran OTP (titre ou message mentionnant "code")
    # Titres réels observés sur l'écran OTP TikTok (FR/EN)
    # "Renvoyer un code" / "Resend code" — toujours présent sur cet écran
    _otp_screen_indicator_base: List[str] = field(default_factory=lambda: [
        # Fallback : 6 EditText d'un seul caractère = grille OTP
        '//android.widget.EditText[string-length(@hint)=1]',
    ])

    @property
    def otp_screen_indicator(self) -> List[str]:
        return self._otp_screen_indicator_base + L("signup.otp_screen_indicator")

    # Champ de saisie du code : peut être un EditText unique (6 chiffres)
    # ou la première case d'une grille à 6 cases
    otp_input: List[str] = field(default_factory=lambda: [
        # Champ unique 6 chiffres
        '//android.widget.EditText[contains(@hint, "code") or contains(@hint, "Code")]',
        # Première case individuelle (grille 6×1)
        '(//android.widget.EditText[@hint="" or string-length(@hint)<=1])[1]',
        # Fallback : premier EditText de l'écran
        '(//android.widget.EditText)[1]',
    ])

    # Bouton "Renvoyer le code" (pour déclencher un renvoi si besoin)
    @property
    def otp_resend_button(self) -> List[str]:
        return L("signup.otp_resend_button")

    # Bouton "Continuer" / "Suivant" après saisie du code
    _otp_continue_button_base: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, "ezo")]',
    ])

    @property
    def otp_continue_button(self) -> List[str]:
        return self._otp_continue_button_base + L("signup.otp_continue_button")

    # ── Écran création du mot de passe ─────────────────────────────────────
    # Dump observé : ui_dump_20260504_021827.xml
    # Titre   : id=e_c  text="Créer un mot de passe" / "Create a password"
    # Input   : EditText hint="Saisis le mot de passe" / "Enter password"
    # Toggle  : ImageView desc="Afficher le mot de passe" / "Show password"
    # Requis  : id=d6h ImageView desc="Exigences de mot de passe non remplies"
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

    # ── Écran création du surnom (username) ────────────────────────────────
    # Dump observé : ui_dump_20260504_021944.xml
    # Titre   : id=e_c  text="Créer un surnom" / "Create a username"
    # Sous-t. : id=e8k  (description optionnelle, modifiable plus tard)
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
    # Corps   : id=e_h  (texte explicatif, scrollable)
    # Bouton  : Button  text="Got it"  (pas de resource-id)
    #
    # Cette popup peut apparaître à n'importe quel moment du flow d'inscription,
    # directement superposée à l'écran en cours (home, profil, etc.).

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
