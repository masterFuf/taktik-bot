"""Selectors for the TikTok logout flow."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L

# ---------------------------------------------------------------------------
# Logout selectors
# ---------------------------------------------------------------------------

@dataclass
class LogoutSelectors:
    """Selectors for the TikTok logout flow.

    Flow observé (app en anglais, dumps 02/05/2026) :
      1. the For You screen, or any screen with the navigation bar
         → onglet "Profile" en bas à droite
      2. the profile page
         -> the menu button at the top right
      3. Menu burger (panneau latéral)
         → "Settings and privacy"
      4. Page Settings and privacy
         → scroll jusqu'en bas → "Log out" (section "Login")
      5. Popup de confirmation (bottom sheet)
         -> the log-out button
    """

    # -- Bottom navigation bar ---------------------------------------

    # Profile tab of the bottom navigation bar
    # resource-id: com.zhiliaoapp.musically:id/nce  content-desc="Profile"
    _profile_tab_base: List[str] = field(default_factory=lambda: [
        '//*[contains(@resource-id, ":id/nce")]',
    ])

    @property
    def profile_tab(self) -> List[str]:
        return self._profile_tab_base + L("logout.profile_tab")

    # -- Profile page ------------------------------------------------

    # Menu button at the top right of the profile page
    # content-desc="Profile menu"
    @property
    def profile_menu_button(self) -> List[str]:
        return L("logout.profile_menu_button")

    # ── Menu burger (panneau latéral) ─────────────────────────────────

    # Settings entry of the menu
    # resource-id: com.zhiliaoapp.musically:id/d_w  content-desc="Settings and privacy"
    settings_and_privacy: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[contains(@resource-id, ":id/d_w") and @content-desc="Settings and privacy"]',
        '//*[@content-desc="Settings and privacy"]',
        '//*[@text="Settings and privacy"]',
    ])

    # ── Page Settings and privacy ─────────────────────────────────────

    # Settings page marker, its title, used to confirm the navigation
    # No resource-id: matched by text and content-desc
    settings_screen_indicator: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Settings and privacy" and @text="Settings and privacy"]',
    ])

    # Log-out button of the settings page, at the very bottom
    # No resource-id: text only
    @property
    def logout_button(self) -> List[str]:
        return L("logout.logout_button")

    # ── Popup de confirmation (bottom sheet) ──────────────────────────

    # Indicateur de la bottom sheet "Are you sure you want to log out?"
    # resource-id: com.zhiliaoapp.musically:id/fdg  content-desc="Bottom sheet"
    logout_confirm_sheet: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[contains(@resource-id, ":id/fdg")]',
        '//*[@content-desc="Bottom sheet"]',
    ])

    # Log-out button of the confirmation popup
    # In the popup the button carries a content-desc, unlike the settings page
    @property
    def logout_confirm_button(self) -> List[str]:
        return L("logout.logout_confirm_button")

    # Cancel button of the popup
    # content-desc="Cancel", resource-id: com.zhiliaoapp.musically:id/wk
    logout_cancel_button: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Cancel"]',
        '//*[@text="Cancel"]',
    ])


LOGOUT_SELECTORS = LogoutSelectors()
