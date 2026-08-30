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
    #: `nce` resolves on NONE of the 61 stored dumps, either version -- the entry of the whole
    #: logout flow pointed at nothing. Kept behind the readable route rather than deleted, in case
    #: it is the id of a build we have not captured.
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
    #: The label was written in ENGLISH, in a neutral file: a French phone reads
    #: « Paramètres et confidentialité » and none of the three alternatives could see it. Through
    #: the locale layer now, like every other visible label in this catalogue.
    _settings_and_privacy_base: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[contains(@resource-id, ":id/d_w")]',
    ])

    @property
    def settings_and_privacy(self) -> List[str]:
        return self._settings_and_privacy_base + L("logout.settings_and_privacy")

    # ── Page Settings and privacy ─────────────────────────────────────

    # Settings page marker, its title, used to confirm the navigation
    # No resource-id: matched by text and content-desc
    @property
    def settings_screen_indicator(self) -> List[str]:
        return L("logout.settings_screen_indicator")

    # Log-out button of the settings page, at the very bottom
    # No resource-id: text only
    @property
    def logout_button(self) -> List[str]:
        return L("logout.logout_button")

    # ── Popup de confirmation (bottom sheet) ──────────────────────────

    # Indicateur de la bottom sheet "Are you sure you want to log out?"
    # resource-id: com.zhiliaoapp.musically:id/fdg  content-desc="Bottom sheet"
    #: Measured on 46.6.3: the sheet is `fxs`, and its content-desc follows the app language
    #: (« Feuille du bas » in French), so the English one alone could not see it.
    _logout_confirm_sheet_base: List[str] = field(default_factory=lambda: [
        '//android.widget.FrameLayout[contains(@resource-id, ":id/fdg")]',
        '//android.widget.FrameLayout[contains(@resource-id, ":id/fxs")]',
    ])

    @property
    def logout_confirm_sheet(self) -> List[str]:
        return self._logout_confirm_sheet_base + L("logout.bottom_sheet")

    # Log-out button of the confirmation popup
    # In the popup the button carries a content-desc, unlike the settings page
    @property
    def logout_confirm_button(self) -> List[str]:
        return L("logout.logout_confirm_button")

    # Cancel button of the popup
    # content-desc="Cancel", resource-id: com.zhiliaoapp.musically:id/wk
    @property
    def logout_cancel_button(self) -> List[str]:
        return L("logout.logout_cancel_button")

    @property
    def logout_sheet_indicator(self) -> List[str]:
        """What the confirmation sheet says. Measured: « Veux-tu vraiment te déconnecter ? »"""
        return L("logout.logout_sheet_indicator")


LOGOUT_SELECTORS = LogoutSelectors()
