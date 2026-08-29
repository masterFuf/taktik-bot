"""Selectors of the TikTok settings -> app language flow.

Walked and measured on a real phone on 2026-08-29, in BOTH directions: the path was captured on a
device whose TikTok was in English, then used to switch it back to French, which is the only test
that proves the flow works from a language you did not start in.

    Profile tab -> profile menu (burger) -> "Settings and privacy"
      -> scroll to "Language" (under "Content & display")
      -> "App language" -> pick the language by its NATIVE name -> "Done"

THE THING THAT MAKES THIS WORK AT ALL: the picker lists every language in its OWN spelling —
`Deutsch`, `Español`, `Čeština`, `Français`, `English (UK)`. Those labels are identical whatever
the current UI language, so the row anchor does not depend on the language we are trying to leave.
Without that, changing the language would require already reading it.

Everything else on the path IS localized and lives in the locale overlay. Measured: selecting a
row does NOT relabel the header — "Done" is still "Done" at the moment it is tapped, and the whole
app only switches after. So the confirm button can be anchored on its label, provided the entry
carries both languages.
"""

from typing import Dict, List
from dataclasses import dataclass, field

from ..locales import L

#: Target language -> the label the picker shows for it, in its own spelling.
#: Read off the real picker; the keys are the codes `ui/language.py` detects.
APP_LANGUAGE_NATIVE_NAMES: Dict[str, str] = {
    "en": "English (UK)",
    "en-GB": "English (UK)",
    "en-US": "English (US)",
    "fr": "Français",
    "fr-FR": "Français",
    "fr-CA": "Français (Canada)",
}


@dataclass
class SettingsSelectors:
    """The settings -> app language path."""

    # === "Settings and privacy", at the bottom of the profile burger menu ===
    @property
    def settings_and_privacy_row(self) -> List[str]:
        return L("settings.settings_and_privacy_row")

    # === "Language", under "Content & display" — needs scrolling to reach ===
    @property
    def language_row(self) -> List[str]:
        return L("settings.language_row")

    # === "App language", the row that opens the picker ===
    #
    # Deliberately NOT the same as `language_row`: the Language screen also carries a
    # Translations section whose rows show language names too ("Translate into: English"). Tapping
    # the wrong one changes what gets translated, not what the app speaks.
    @property
    def app_language_row(self) -> List[str]:
        return L("settings.app_language_row")

    # === The picker ===
    #: A row of the picker is a clickable ViewGroup holding the native-name TextView. Addressed by
    #: climbing from the label, the same way the post grid and the search results are.
    def language_row_for_native_name(self, native_name: str) -> List[str]:
        escaped = str(native_name or "").replace('"', "")
        return [
            f'//android.widget.TextView[@text="{escaped}"]/ancestor::*[@clickable="true"][1]',
            f'//*[@text="{escaped}"][@clickable="true"]',
        ]

    #: The picker itself, to know it opened before scrolling inside it.
    @property
    def picker_indicator(self) -> List[str]:
        return L("settings.picker_indicator")

    @property
    def picker_confirm_button(self) -> List[str]:
        return L("settings.picker_confirm_button")

    @property
    def picker_cancel_button(self) -> List[str]:
        return L("settings.picker_cancel_button")

    # === Back arrow of the settings screens ===
    _settings_back_button_base: List[str] = field(default_factory=lambda: [
        '//*[@content-desc="Back to previous screen"]',
    ])

    @property
    def settings_back_button(self) -> List[str]:
        return self._settings_back_button_base + L("settings.settings_back_button")


SETTINGS_SELECTORS = SettingsSelectors()

__all__ = ["APP_LANGUAGE_NATIVE_NAMES", "SETTINGS_SELECTORS", "SettingsSelectors"]
