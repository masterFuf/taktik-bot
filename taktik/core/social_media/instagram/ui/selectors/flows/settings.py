"""Selectors for the Instagram "Settings and activity" → language flow.

Reaching the settings screen (Profile tab → "Options") reuses ``AUTH_SELECTORS``
(``profile_tab_button`` / ``profile_options_button`` / ``settings_screen_indicators``),
so this catalog only covers the language-specific path *beyond* the settings list:
the "Language and translations" row, the "Set language" sub-row, and the app
language picker.

Provenance: real device dumps (Instagram, 2026-06-22), captured
in FR and EN. Neutral ``resource-id`` parts are dataclass fields; the localized
row labels live in the per-language overlay (``locales/{en,fr}.py``) and are read
via ``L("settings.<field>")``. The picker rows are matched by their NATIVE
language name (``com.instagram.android:id/language_name``) — which is identical in
every UI language — through :meth:`SettingsSelectors.language_row_for`, so the
final selection is robust whatever the current app language is.
"""

from typing import Dict, List
from dataclasses import dataclass, field

from ..locales import L


# Native language labels exactly as shown in the IG app-language picker
# (``com.instagram.android:id/language_name``). Mapping: stable language code sent
# by the desktop -> native picker label. Native labels are identical in every UI
# language, so they double as the match value for
# :meth:`SettingsSelectors.language_row_for`. Scope: FR + EN variants (see the bot
# CHANGELOG). Extend this map to widen the supported target languages.
APP_LANGUAGE_NATIVE_NAMES: Dict[str, str] = {
    "en": "English",
    "en-GB": "English (UK)",
    "fr-FR": "Français (France)",
    "fr-CA": "Français (Canada)",
}


@dataclass
class SettingsSelectors:
    """Selectors of the settings -> language flow (beyond the settings list)."""

    # === "Language and translations" row ===
    # The settings list rows carry no resource-id, so they are targeted by text.
    @property
    def language_and_translations_row(self) -> List[str]:
        return L("settings.language_and_translations_row")

    # === "Set language" row (language sub-screen) ===
    # Neutral resource-id plus localized text: the sub-screen holds several rows of the
    # same type, so the label stays necessary to disambiguate.
    @property
    def set_language_row(self) -> List[str]:
        return L("settings.set_language_row")

    # Markers of the app-language picker (neutral).
    language_picker_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/language_name"]',
        '//*[@resource-id="com.instagram.android:id/search"]',
    ])

    # resource-id carried by each language native name in the picker.
    language_name_resource_id: str = "com.instagram.android:id/language_name"

    def language_row_for(self, native_name: str) -> List[str]:
        """Selectors of one picker row, targeted by its EXACT NATIVE name.

        A native label is identical whatever the current interface language, so this
        match works regardless of the language the app is currently in.

        EXACT match only, never ``contains``: one language name can be a prefix of
        another variant, and a loose match would let the scroll-until-found loop stop
        on the wrong variant, tap the wrong language, and still report success.
        """
        rid = self.language_name_resource_id
        return [
            f'//*[@resource-id="{rid}" and @text="{native_name}"]',
            f'//android.widget.TextView[@text="{native_name}"]',
        ]


SETTINGS_SELECTORS = SettingsSelectors()
