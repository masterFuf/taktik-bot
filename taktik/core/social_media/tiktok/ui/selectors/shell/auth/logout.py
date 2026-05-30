"""Selectors for the TikTok logout flow."""

from typing import List
from dataclasses import dataclass, field

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
