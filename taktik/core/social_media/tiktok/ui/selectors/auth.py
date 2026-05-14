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
    signup_link: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/mwu")]',
        '//android.widget.Button[contains(@text, "Inscription")]',
        '//android.widget.Button[contains(@text, "Sign up")]',
    ])

    # ── Indicateur popup "Inscription à TikTok" ────────────────────────────

    # Titre de la popup d'inscription : id=title text="Inscription à TikTok" (trill) /
    # "Sign up for TikTok" (EN). Apparaît juste après la birthday gate.
    # resource-id: com.zhiliaoapp.musically:id/title
    signup_popup_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/title") and contains(@text, "Inscription")]',
        '//android.widget.TextView[contains(@resource-id, ":id/title") and contains(@text, "Sign up")]',
        # NOTE: removed the generic contains(@text, "TikTok") selector — too broad,
        # it matched the birthday screen title on some Samsung devices.
        # Compose-based UI: title has no resource-id — match by full precise text
        '//android.widget.TextView[contains(@text, "Sign up for TikTok")]',
        '//android.widget.TextView[contains(@text, "Inscription") and contains(@text, "TikTok")]',
        # "Use phone or email" button is unique to this popup (not on birthday gate)
        '//*[@content-desc="Use phone or email"]',
        '//*[@content-desc="Utiliser un numéro de téléphone ou une adresse e-mail"]',
    ])

    # ── Lien "Inscription" sur la birthday gate ────────────────────────────

    # Sur la page birthday gate (pré-inscription), un bouton en bas invite
    # à s'inscrire : id=mfb text="Plus de fonctionnalités intéressantes ? Inscription"
    # (FR) / "More fun features? Sign up" (EN). Permet de distinguer cette
    # birthday gate de la birthday screen dans le flow d'inscription.
    # resource-id: com.zhiliaoapp.musically:id/mfb
    birthday_gate_inscription_link: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/mfb")]',
        '//android.widget.Button[contains(@text, "fonctionnalités") and contains(@text, "Inscription")]',
        '//android.widget.Button[contains(@text, "More fun") and contains(@text, "Sign up")]',
        # Generic fallbacks — safe because signup_popup_indicator (whose title
        # TextView also mentions "Inscription") is checked first in _detect_screen().
        '//android.widget.Button[contains(@text, "Inscription")]',
        '//android.widget.Button[contains(@text, "Sign up")]',
        # Also cover cases where the element is a TextView or generic View
        '//*[@clickable="true" and contains(@text, "Inscription")]',
        '//*[@clickable="true" and contains(@text, "Sign up")]',
        '//*[@clickable="true" and (contains(@text, "inscrire") or contains(@content-desc, "inscrire"))]',
    ])

    # ── Écran date de naissance ────────────────────────────────────────────

    # Indicateur de l'écran date de naissance
    # resource-id musically: com.zhiliaoapp.musically:id/aby
    # resource-id trill:     com.ss.android.ugc.trill:id/aac  (patché → id/aac)
    birthday_screen_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/aby")]',
        '//android.widget.TextView[contains(@resource-id, ":id/aac")]',
        '//android.widget.TextView[contains(@text, "date de naissance")]',
        '//android.widget.TextView[contains(@text, "date of birth")]',
        '//android.widget.TextView[contains(@text, "birthday")]',
        '//android.widget.TextView[contains(@text, "naissance")]',
        '//android.widget.TextView[contains(@text, "anniversaire")]',
        # Fallback: the birthday picker always has ≥3 scrollable SeekBars
        # (day / month / year wheels). Video scrubbers only have 1, so [3]
        # ensures this only matches a true birthday picker screen.
        '//android.widget.SeekBar[@scrollable="true"][3]',
    ])

    # Champ texte "Date de naissance" — affiche la date sélectionnée en temps réel
    # resource-id musically: com.zhiliaoapp.musically:id/kcl
    # resource-id trill:     com.ss.android.ugc.trill:id/jsh  (patché → id/jsh)
    # Valeurs possibles : "10 juin 2025" / "10 June 2025" / placeholder hint
    birthday_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@resource-id, ":id/kcl")]',
        '//android.widget.EditText[contains(@resource-id, ":id/jsh")]',
        '//android.widget.EditText[contains(@hint, "naissance")]',
        '//android.widget.EditText[@hint="Birthday"]',
        '//android.widget.EditText[@hint="Date of birth"]',
        '(//android.widget.EditText)[1]',
    ])

    # SeekBar (roue déroulante) – jour
    # resource-id musically: com.zhiliaoapp.musically:id/f53  content-desc: "Sélecteur du jour"
    # resource-id trill:     com.ss.android.ugc.trill:id/erv  (patché → id/erv)
    birthday_day_picker: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/f53")]',
        '//android.widget.SeekBar[contains(@resource-id, ":id/erv")]',
        '//android.widget.SeekBar[@content-desc="Day picker"]',
        '//android.widget.SeekBar[@content-desc="Sélecteur du jour"]',
        '(//android.widget.SeekBar[@scrollable="true"])[1]',
    ])

    # SeekBar – mois
    # resource-id musically: com.zhiliaoapp.musically:id/o18  content-desc: "Sélecteur du mois"
    # resource-id trill:     com.ss.android.ugc.trill:id/n7o  (patché → id/n7o)
    birthday_month_picker: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/o18")]',
        '//android.widget.SeekBar[contains(@resource-id, ":id/n7o")]',
        '//android.widget.SeekBar[@content-desc="Month picker"]',
        '//android.widget.SeekBar[@content-desc="Sélecteur du mois"]',
        '(//android.widget.SeekBar[@scrollable="true"])[2]',
    ])

    # SeekBar – année
    # resource-id: com.zhiliaoapp.musically:id/year_picker  content-desc: "Sélecteur de l'année"
    birthday_year_picker: List[str] = field(default_factory=lambda: [
        '//android.widget.SeekBar[contains(@resource-id, ":id/year_picker")]',
        '//android.widget.SeekBar[@content-desc="Year picker"]',
        '//android.widget.SeekBar[@content-desc="Sélecteur de l\'année"]',
        '(//android.widget.SeekBar[@scrollable="true"])[3]',
    ])

    # Bouton "Continuer" sur l'écran date de naissance
    # resource-id musically: com.zhiliaoapp.musically:id/ac8
    # resource-id trill:     com.ss.android.ugc.trill:id/aal  (patché → id/aal)
    birthday_continue_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/ac8")]',
        '//android.widget.Button[contains(@resource-id, ":id/aal")]',
        '//android.widget.Button[@text="Continuer"]',
        '//android.widget.Button[@text="Continue"]',
    ])

    # ── Écran choix de la méthode d'inscription ────────────────────────────

    # Bouton "Utiliser un numéro de téléphone ou une adresse e-mail"
    # Sur la popup signup : id=e52, content-desc="Utiliser un numéro de téléphone ou une adresse e-mail"
    # resource-id: com.zhiliaoapp.musically:id/e52
    use_phone_or_email_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/e52") and contains(@content-desc, "téléphone")]',
        '//android.widget.Button[contains(@resource-id, ":id/e52") and contains(@content-desc, "phone")]',
        '//*[@content-desc="Use phone or email"]',
        '//*[@content-desc="Utiliser un numéro de téléphone ou une adresse e-mail"]',
        '//*[contains(@content-desc, "numéro de téléphone") and contains(@content-desc, "e-mail")]',
        '//*[contains(@content-desc, "phone") and contains(@content-desc, "email")]',
        # Compose button: clickable parent has no content-desc; child TextView has the text
        '//*[@clickable="true" and ./android.widget.TextView[@text="Use phone or email"]]',
        '//*[@clickable="true" and ./android.widget.TextView[contains(@text, "phone") and contains(@text, "email")]]',
        '//*[contains(@text, "numéro de téléphone") and contains(@text, "e-mail")]',
        '//*[contains(@text, "Use phone or email")]',
    ])

    # ── Écran saisie téléphone / email (onglets) ───────────────────────────

    # Indicateur de l'écran inscription (titre)
    # resource-id: com.zhiliaoapp.musically:id/ohi  text="Inscription"
    register_screen_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/ohi")]',
        '//android.widget.TextView[@content-desc="Inscription"]',
        '//android.widget.TextView[@content-desc="Sign up"]',
        '//android.widget.TextView[@text="Inscription"]',
    ])

    # Onglet "Téléphone"  (content-desc="Téléphone", selected quand actif)
    tab_phone: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Phone" and @clickable="true"]',
        '//android.widget.LinearLayout[@content-desc="Phone"]',
        '//*[@content-desc="Téléphone" and @clickable="true"]',
        '//android.widget.LinearLayout[@content-desc="Téléphone"]',
    ])

    # Onglet "E-mail"
    tab_email: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Email" and @clickable="true"]',
        '//android.widget.LinearLayout[@content-desc="Email"]',
        '//*[@content-desc="E-mail" and @clickable="true"]',
        '//android.widget.LinearLayout[@content-desc="E-mail"]',
    ])

    # Sélecteur du code pays (bouton "US +1" dans l'onglet Téléphone)
    # resource-id: com.zhiliaoapp.musically:id/ps9  (LinearLayout cliquable)
    country_code_selector: List[str] = field(default_factory=lambda: [
        '//android.widget.LinearLayout[contains(@resource-id, ":id/ps9") and @clickable="true"]',
        '//*[.//android.widget.TextView[contains(@resource-id, ":id/eqh")]]',
    ])

    # Champ numéro de téléphone (hint="Numéro de téléphone", pas de resource-id)
    phone_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@hint="Numéro de téléphone"]',
        '//android.widget.EditText[@hint="Phone number"]',
        '//android.widget.EditText[contains(@hint, "téléphone")]',
        '//android.widget.EditText[contains(@hint, "phone")]',
    ])

    # Champ adresse e-mail (hint="Adresse e-mail", pas de resource-id)
    email_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@hint="Adresse e-mail"]',
        '//android.widget.EditText[@hint="Email address"]',
        '//android.widget.EditText[contains(@hint, "e-mail")]',
        '//android.widget.EditText[contains(@hint, "email")]',
    ])

    # Bouton "Continuer" sur l'écran téléphone/email
    # resource-id: com.zhiliaoapp.musically:id/ezo  (commun aux deux onglets)
    continue_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/ezo")]',
        '//android.widget.Button[@text="Continuer"]',
        '//android.widget.Button[@text="Continue"]',
    ])

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
    back_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@content-desc="Retour à l\'écran précédent"]',
        '//android.widget.Button[@content-desc="Go back"]',
        '//android.widget.Button[@content-desc="Navigate up"]',
    ])

    # ── Écran saisie du code de vérification (OTP) ─────────────────────────
    # Cet écran apparaît après la saisie de l'email ou du téléphone.
    # TikTok envoie un code à 6 chiffres et affiche un champ de saisie.
    # Note : les resource-id exacts seront confirmés avec un dump de cet écran.

    # Indicateur de l'écran OTP (titre ou message mentionnant "code")
    otp_screen_indicator: List[str] = field(default_factory=lambda: [
        # Titres réels observés sur l'écran OTP TikTok (FR/EN)
        '//android.widget.TextView[contains(@text, "Consulte tes e-mails")]',
        '//android.widget.TextView[contains(@text, "Check your email")]',
        '//android.widget.TextView[contains(@text, "Utilise le lien ou code")]',
        '//android.widget.TextView[contains(@text, "Use the link or code")]',
        '//android.widget.TextView[contains(@text, "code de vérification")]',
        '//android.widget.TextView[contains(@text, "verification code")]',
        '//android.widget.TextView[contains(@text, "Entrez le code")]',
        '//android.widget.TextView[contains(@text, "Enter the code")]',
        '//android.widget.TextView[contains(@text, "Enter code")]',
        '//android.widget.TextView[contains(@text, "Saisir le code")]',
        # "Renvoyer un code" / "Resend code" — toujours présent sur cet écran
        '//*[contains(@text, "Renvoyer un code")]',
        '//*[contains(@text, "Resend code")]',
        # Fallback : 6 EditText d'un seul caractère = grille OTP
        '//android.widget.EditText[string-length(@hint)=1]',
    ])

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
    otp_resend_button: List[str] = field(default_factory=lambda: [
        '//*[contains(@text, "Renvoyer") and contains(@text, "code")]',
        '//*[contains(@text, "Resend") and contains(@text, "code")]',
        '//*[contains(@content-desc, "Resend")]',
    ])

    # Bouton "Continuer" / "Suivant" après saisie du code
    otp_continue_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Continuer"]',
        '//android.widget.Button[@text="Continue"]',
        '//android.widget.Button[contains(@resource-id, "ezo")]',
    ])

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

    password_entry_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/e_c") and contains(@text, "mot de passe")]',
        '//android.widget.TextView[contains(@resource-id, ":id/e_c") and contains(@text, "password")]',
        '//android.widget.TextView[contains(@text, "Créer un mot de passe")]',
        '//android.widget.TextView[contains(@text, "Create a password")]',
        # Requirement indicator is unique to this screen
        '//android.widget.ImageView[contains(@resource-id, ":id/d6h")]',
    ])

    password_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@hint="Saisis le mot de passe"]',
        '//android.widget.EditText[@hint="Enter password"]',
        '//android.widget.EditText[contains(@hint, "mot de passe")]',
        '//android.widget.EditText[contains(@hint, "password")]',
    ])

    password_continue_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/emm")]',
        '//android.widget.Button[@text="Continuer"]',
        '//android.widget.Button[@text="Continue"]',
    ])

    password_skip_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Ignorer"]',
        '//android.widget.Button[@text="Skip"]',
    ])

    # ── Écran création du surnom (username) ────────────────────────────────
    # Dump observé : ui_dump_20260504_021944.xml
    # Titre   : id=e_c  text="Créer un surnom" / "Create a username"
    # Sous-t. : id=e8k  (description optionnelle, modifiable plus tard)
    # Input   : EditText hint="Ajoute ton surnom" / "Add your username"
    # Compteur: id=fuh  text="0/30"
    # Skip    : Button text="Ignorer" / "Skip"
    # Valider : id=emm Button text="Continuer" / "Continue"

    nickname_entry_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/e_c") and contains(@text, "surnom")]',
        '//android.widget.TextView[contains(@resource-id, ":id/e_c") and contains(@text, "username")]',
        '//android.widget.TextView[contains(@text, "Créer un surnom")]',
        '//android.widget.TextView[contains(@text, "Create a username")]',
        # Counter "0/30" is unique to this screen
        '//android.widget.TextView[contains(@resource-id, ":id/fuh")]',
    ])

    nickname_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[@hint="Ajoute ton surnom"]',
        '//android.widget.EditText[@hint="Add your username"]',
        '//android.widget.EditText[contains(@hint, "surnom")]',
        '//android.widget.EditText[contains(@hint, "username")]',
    ])

    nickname_continue_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[contains(@resource-id, ":id/emm")]',
        '//android.widget.Button[@text="Continuer"]',
        '//android.widget.Button[@text="Continue"]',
    ])

    nickname_skip_button: List[str] = field(default_factory=lambda: [
        '//android.widget.Button[@text="Ignorer"]',
        '//android.widget.Button[@text="Skip"]',
    ])

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
    ])


SIGNUP_SELECTORS = SignupSelectors()


# ---------------------------------------------------------------------------
# Sélecteurs pour le sélecteur de pays (country picker)
# ---------------------------------------------------------------------------

@dataclass
class CountryPickerSelectors:
    """Sélecteurs pour l'écran "Select country/region".

    Dump observé : ui_dump_20260502_141800.xml
    Apparaît quand l'utilisateur tape sur le bouton de code pays (+XX)
    dans l'onglet Téléphone de l'écran d'inscription.

    Éléments clés :
      - Titre           : id=title  text="Select country/region"
      - Bouton fermer   : id=be6    content-desc="Close"
      - Champ recherche : id=tlr    hint="Search countries and regions"  (EditText)
      - Liste pays      : id=t7v    (RecyclerView)
        - Ligne         : id=eqo    (LinearLayout)
          - Nom pays    : id=z83    (TextView)
          - Code phone  : id=ynw    (TextView, ex: "+33")
    """

    # Indicateur de l'écran
    # resource-id: com.zhiliaoapp.musically:id/title  text="Select country/region"
    screen_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@resource-id, ":id/title") and @text="Select country/region"]',
        '//android.widget.TextView[@text="Select country/region"]',
    ])

    # Bouton fermer (croix en haut à gauche)
    # resource-id: com.zhiliaoapp.musically:id/be6  content-desc="Close"
    close_button: List[str] = field(default_factory=lambda: [
        '//android.widget.ImageView[contains(@resource-id, ":id/be6") and @content-desc="Close"]',
        '//*[@content-desc="Close"]',
    ])

    # Champ de recherche des pays
    # resource-id: com.zhiliaoapp.musically:id/tlr  hint="Search countries and regions"
    search_input: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@resource-id, ":id/tlr")]',
        '//android.widget.EditText[@hint="Search countries and regions"]',
        '//android.widget.EditText[contains(@hint, "countries")]',
    ])

    # Premier élément de la liste des pays (après filtrage par recherche)
    # resource-id: com.zhiliaoapp.musically:id/eqo  (LinearLayout cliquable)
    first_country_item: List[str] = field(default_factory=lambda: [
        '(//android.widget.LinearLayout[contains(@resource-id, ":id/eqo")])[1]',
        '(//android.widget.LinearLayout[.//android.widget.TextView[contains(@resource-id, ":id/z83")]])[1]',
    ])


COUNTRY_PICKER_SELECTORS = CountryPickerSelectors()


# ---------------------------------------------------------------------------
# Sélecteurs pour la déconnexion (logout)
# ---------------------------------------------------------------------------

@dataclass
class LogoutSelectors:
    """Sélecteurs pour le flow de déconnexion TikTok.

    Flow observé (app en anglais, dumps 02/05/2026) :
      1. Écran For You (ou tout écran avec barre de nav)
         → onglet "Profile" en bas à droite
      2. Page profil
         → bouton burger ≡ (content-desc="Profile menu") en haut à droite
      3. Menu burger (panneau latéral)
         → "Settings and privacy"
      4. Page Settings and privacy
         → scroll jusqu'en bas → "Log out" (section "Login")
      5. Popup de confirmation (bottom sheet)
         → bouton "Log out" (en rouge, content-desc="Log out")
    """

    # ── Barre de navigation du bas ────────────────────────────────────

    # Onglet "Profile" dans la barre de navigation du bas
    # resource-id: com.zhiliaoapp.musically:id/nce  content-desc="Profile"
    profile_tab: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nce")]',
        '//*[@content-desc="Profile"][contains(@resource-id, ":id/nce")]',
        '//*[@content-desc="Profile" and @clickable="true"]',
    ])

    # ── Page de profil ────────────────────────────────────────────────

    # Bouton burger ≡ en haut à droite de la page profil
    # content-desc="Profile menu"
    profile_menu_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Profile menu"]',
    ])

    # ── Menu burger (panneau latéral) ─────────────────────────────────

    # Élément "Settings and privacy" dans le menu burger
    # resource-id: com.zhiliaoapp.musically:id/d_w  content-desc="Settings and privacy"
    settings_and_privacy: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[contains(@resource-id, ":id/d_w") and @content-desc="Settings and privacy"]',
        '//*[@content-desc="Settings and privacy"]',
        '//*[@text="Settings and privacy"]',
    ])

    # ── Page Settings and privacy ─────────────────────────────────────

    # Indicateur de la page Settings and privacy (titre, pour confirmer la navigation)
    # Pas de resource-id — repéré par text + content-desc
    settings_screen_indicator: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Settings and privacy" and @text="Settings and privacy"]',
    ])

    # Bouton "Log out" dans la page Settings (section "Login", tout en bas)
    # Pas de resource-id – seulement le text
    logout_button: List[str] = field(default_factory=lambda: [
        '//*[@text="Log out"]',
        '//*[@text="Se déconnecter"]',
        '//*[@text="Déconnexion"]',
    ])

    # ── Popup de confirmation (bottom sheet) ──────────────────────────

    # Indicateur de la bottom sheet "Are you sure you want to log out?"
    # resource-id: com.zhiliaoapp.musically:id/fdg  content-desc="Bottom sheet"
    logout_confirm_sheet: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[contains(@resource-id, ":id/fdg")]',
        '//*[@content-desc="Bottom sheet"]',
    ])

    # Bouton "Log out" dans la popup (en rouge) — confirme la déconnexion
    # Dans la popup : content-desc="Log out" (différent de la page settings qui n'a que @text)
    logout_confirm_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Log out"]',
        '//*[contains(@resource-id, ":id/wk") and @text="Log out"]',
    ])

    # Bouton "Cancel" dans la popup
    # content-desc="Cancel", resource-id: com.zhiliaoapp.musically:id/wk
    logout_cancel_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Cancel"]',
        '//*[@text="Cancel"]',
    ])


LOGOUT_SELECTORS = LogoutSelectors()
