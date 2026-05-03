"""
Gmail UI Selectors

All XPath selectors for the Gmail Android app (com.google.android.gm)
and the Google account sign-in WebView (com.google.android.gms).

Sources
-------
UI dumps captured 02/05/2026 on device running Samsung Android.
Screens covered:
  - Account switcher overlay (og_bento_*)
  - "Configurez votre adresse e-mail" setup screen (account_setup_*)
  - Google "Connexion" sign-in WebView (com.google.android.gms)
  - Gmail inbox + conversation thread (runtime IDs)

Note on WebView
---------------
The Google sign-in flow (email + password) is rendered inside a WebView
owned by com.google.android.gms. Element IDs inside the WebView are NOT
accessible via uiautomator2. Selectors for these screens are therefore
coordinate-based helpers defined in the workflow (not here).
The "Suivant"/"Next" button lives OUTSIDE the WebView and IS accessible.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class _GmailAccountSwitcherSelectors:
    """Account switcher overlay (tap avatar to open)."""

    # Ouverture — avatar en haut à droite dans la barre Gmail
    # NOTE: plusieurs IDs possibles selon la version de Gmail ;
    #       dans le dump : 'og_bento_selected_account_avatar'
    avatar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/selected_account_disc_gmail"]',
        '//*[@resource-id="com.google.android.gm:id/og_bento_selected_account_avatar"]',
        '//*[@resource-id="com.google.android.gm:id/og_bento_selected_account_avatar_circle"]',
        '//*[@package="com.google.android.gm"]'
        '[contains(@content-desc,"Compte et paramètres")]',
        '//*[@package="com.google.android.gm"]'
        '[contains(@content-desc,"Account and settings")]',
    ])

    # Indicateur de l'overlay ouvert
    screen_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/og_bento_account_menu_title_text"]',
        '//*[@resource-id="com.google.android.gm:id/og_bento_selected_account_greeting_message"]',
    ])

    # Email du compte actuellement affiché (titre de l'overlay)
    current_account_email: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/og_bento_account_menu_title_text"]',
    ])

    # Lignes de comptes dans la liste "Changer de compte"
    # og_secondary_account_information = email ; og_primary_account_information = nom
    account_row_email: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/og_secondary_account_information"]',
    ])

    # Bouton "Ajouter un autre compte"
    add_account: List[str] = field(default_factory=lambda: [
        '//*[@clickable="true"]'
        '[.//*[@resource-id="com.google.android.gm:id/og_bento_card_title"]'
        '[@text="Ajouter un autre compte"]]',
        '//*[@clickable="true"]'
        '[.//*[@resource-id="com.google.android.gm:id/og_bento_card_title"]'
        '[@text="Add another account"]]',
        '//*[@resource-id="com.google.android.gm:id/og_bento_card_title"]'
        '[@text="Ajouter un autre compte"]',
        '//*[@resource-id="com.google.android.gm:id/og_bento_card_title"]'
        '[@text="Add another account"]',
    ])

    # Bouton Fermer (×) de l'overlay
    close: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/og_bento_toolbar_close_button"]',
    ])


@dataclass
class _GmailSetupSelectors:
    """'Configurez votre adresse e-mail' – choix du fournisseur."""

    # Indicateur de cet écran
    screen_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/suc_layout_title"]'
        '[@text="Configurez votre adresse e-mail"]',
        '//*[@resource-id="com.google.android.gm:id/suc_layout_title"]'
        '[@text="Set up email"]',
    ])

    # Ligne cliquable du fournisseur — contient le label via account_setup_label
    # On cible l'élément parent account_setup_item ayant un enfant "Google"
    google_row: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/account_setup_item"]'
        '[.//*[@text="Google"]]',
        # fallback: cliquer directement sur le label
        '//*[@resource-id="com.google.android.gm:id/account_setup_label"]'
        '[@text="Google"]',
    ])


@dataclass
class _GoogleSigninSelectors:
    """
    Google "Connexion" screen (com.google.android.gms).

    The email/password fields are inside a WebView and inaccessible via
    resource-id. Only the "Suivant"/"Next" button is reachable.
    """

    # Indicateur de l'écran de connexion Google (présence du bouton Suivant
    # dans le layout com.google.android.gms)
    screen_indicator: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Suivant"]',
        '//*[@package="com.google.android.gms"][@text="Next"]',
    ])

    # Bouton "Suivant" / "Next" (hors WebView — accessible)
    next_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Suivant"]',
        '//*[@package="com.google.android.gms"][@text="Next"]',
    ])

    # Bouton "Suivant" visible sur l'écran mot de passe (même sélecteur)
    password_next_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Suivant"]',
        '//*[@package="com.google.android.gms"][@text="Next"]',
    ])

    # Écran "Accepter" les CGU Google
    accept_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="J\'accepte"]',
        '//*[@package="com.google.android.gms"][@text="I agree"]',
        '//*[@package="com.google.android.gms"][@text="Accepter"]',
        '//*[@package="com.google.android.gms"][@text="Accept"]',
    ])

    # "Continuer" après ToS sur certains firmwares
    continue_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Continuer"]',
        '//*[@package="com.google.android.gms"][@text="Continue"]',
    ])

    # Indicateur d'erreur : mauvais mot de passe / mauvais email
    error_indicator: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][contains(@text,"incorrect")]',
        '//*[@package="com.google.android.gms"][contains(@text,"inexact")]',
        '//*[@package="com.google.android.gms"][contains(@text,"wrong")]',
    ])


@dataclass
class _GoogleVerifyIdentitySelectors:
    """
    Google 'Confirmez qu'il s'agit bien de vous' challenge screen.

    Appears on first login from a new device.  The screen lists several
    verification methods as clickable android.view.View items with
    content-desc identifying each option.

    Source: UI dump 2026-05-02 on OUKITEL C57 S (Android 14).
    """

    # Option 1 — receive code at recovery email (best to automate).
    # The content-desc is "Recevoir un code de validation sur <masked-email>"
    # Identified in dump as clickable android.view.View at bounds [0,575][576,688].
    receive_code: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@clickable="true"]'
        '[contains(@content-desc,"Recevoir un code de validation")]',
        '//*[@package="com.google.android.gms"][@clickable="true"]'
        '[contains(@content-desc,"Receive a verification code")]',
        # Fallback: parent of the label text
        '//*[@package="com.google.android.gms"][@clickable="true"]'
        '[.//*[contains(@text,"Recevoir un code de validation")]]',
        '//*[@package="com.google.android.gms"][@clickable="true"]'
        '[.//*[contains(@text,"Receive a verification code")]]',
    ])

    # "Envoyer" / "Send" button on the send-confirmation step that
    # follows after choosing receive_code.
    send_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Envoyer"]',
        '//*[@package="com.google.android.gms"][@text="Send"]',
    ])

    # Code entry "Suivant" / "Vérifier" used after typing the received code.
    confirm_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Suivant"]',
        '//*[@package="com.google.android.gms"][@text="Next"]',
        '//*[@package="com.google.android.gms"][@text="Vérifier"]',
        '//*[@package="com.google.android.gms"][@text="Verify"]',
    ])


@dataclass
class _GoogleRecoveryOptionsSelectors:
    """
    Google 'Account Recovery Options' screen.

    Shown after successful login on a new device.  Title:
    'Assurez-vous de toujours pouvoir vous connecter'.
    Contains optional phone + recovery-email fields and two buttons.

    Source: UI dump 2026-05-02 on OUKITEL C57 S (Android 14).
    """

    # "Annuler" — skip adding recovery info (preferred bot action).
    # Real android.widget.Button directly accessible.
    cancel_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Annuler"]',
        '//*[@package="com.google.android.gms"][@text="Cancel"]',
    ])

    # "Enregistrer" — save changes (only used if caller wants to save).
    save_button: List[str] = field(default_factory=lambda: [
        '//*[@package="com.google.android.gms"][@text="Enregistrer"]',
        '//*[@package="com.google.android.gms"][@text="Save"]',
    ])


@dataclass
class _GmailInboxSelectors:
    """Gmail inbox and conversation list."""

    # Barre de recherche Gmail (en haut)
    search_bar: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/open_search"]',
        '//*[@resource-id="com.google.android.gm:id/search_bar"]',
        '//*[@resource-id="com.google.android.gm:id/search_src_text"]',
    ])

    # Champ de texte de recherche (après avoir tapé sur la barre)
    search_input: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/open_search"]',
        '//*[@resource-id="com.google.android.gm:id/search_src_text"]',
        '//android.widget.EditText',
    ])

    # Liste des conversations dans la boîte de réception
    conversation_list: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/thread_list_view"]',
        '//*[@resource-id="com.google.android.gm:id/conversation_list_view"]',
    ])

    # Premier résultat de conversation (après recherche)
    first_conversation: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/thread_list_view"]'
        '//*[@resource-id="com.google.android.gm:id/senders"]',
        '//*[@resource-id="com.google.android.gm:id/thread_list_view"]'
        '//android.widget.FrameLayout[@clickable="true"]',
        '//*[@resource-id="com.google.android.gm:id/conversation_list_view"]'
        '//*[@resource-id="com.google.android.gm:id/sender"]',
        # fallback: premier élément cliquable dans la liste
        '//*[@resource-id="com.google.android.gm:id/conversation_list_view"]'
        '//android.widget.LinearLayout[@clickable="true"]',
    ])

    # Corps du message ouvert
    message_body: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/message_body"]',
        '//*[@resource-id="com.google.android.gm:id/body"]',
        # WebView fallback
        '//android.webkit.WebView',
    ])

    # Indicateur que l'inbox est affichée (barre de recherche OU liste)
    inbox_indicator: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.google.android.gm:id/open_search"]',
        '//*[@resource-id="com.google.android.gm:id/thread_list_view"]',
        '//*[@resource-id="com.google.android.gm:id/search_bar"]',
        '//*[@resource-id="com.google.android.gm:id/conversation_list_view"]',
    ])


# ── Singleton instances (importable) ────────────────────────────────────────

GMAIL_SWITCHER_SELECTORS     = _GmailAccountSwitcherSelectors()
GMAIL_SETUP_SELECTORS        = _GmailSetupSelectors()
GOOGLE_SIGNIN_SELECTORS      = _GoogleSigninSelectors()
GOOGLE_VERIFY_SELECTORS      = _GoogleVerifyIdentitySelectors()
GOOGLE_RECOVERY_SELECTORS    = _GoogleRecoveryOptionsSelectors()
GMAIL_INBOX_SELECTORS        = _GmailInboxSelectors()
