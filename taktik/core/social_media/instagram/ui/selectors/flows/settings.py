"""Selectors for the Instagram "Settings and activity" → language flow.

Reaching the settings screen (Profile tab → "Options") reuses ``AUTH_SELECTORS``
(``profile_tab_button`` / ``profile_options_button`` / ``settings_screen_indicators``),
so this catalog only covers the language-specific path *beyond* the settings list:
the "Language and translations" row, the "Set language" sub-row, and the app
language picker.

Provenance: real device dumps (device 9CHAY1PN, Instagram, 2026-06-22), captured
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
    """Sélecteurs du flux Réglages → langue (au-delà de la liste des réglages)."""

    # === Ligne "Langue et traduction" / "Language and translations" ===
    # Les lignes de la liste réglages n'ont pas de resource-id : on cible le texte.
    @property
    def language_and_translations_row(self) -> List[str]:
        return L("settings.language_and_translations_row")

    # === Ligne "Définir la langue" / "Set language" (sous-écran langue) ===
    # resource-id neutre + texte localisé : le sous-écran contient plusieurs
    # row_simple_text_title, donc le libellé reste nécessaire pour désambiguïser.
    @property
    def set_language_row(self) -> List[str]:
        return L("settings.set_language_row")

    # Indicateurs d'arrivée sur le picker "Langue de l'application" (neutres).
    language_picker_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/language_name"]',
        '//*[@resource-id="com.instagram.android:id/search"]',
    ])

    # resource-id porté par le nom natif de chaque langue dans le picker.
    language_name_resource_id: str = "com.instagram.android:id/language_name"

    def language_row_for(self, native_name: str) -> List[str]:
        """Sélecteurs d'une ligne du picker, ciblée par son nom NATIF EXACT.

        Le libellé natif (ex. ``"English"``, ``"Français (France)"``) est identique
        dans toutes les langues de l'app, donc cette correspondance fonctionne quelle
        que soit la langue courante de l'interface.

        Correspondance EXACTE uniquement (pas de ``contains``) : ``"English"`` est un
        préfixe de ``"English (UK)"`` ; un ``contains`` laisserait la boucle
        scroll-jusqu'à-trouvé s'arrêter sur une variante et cliquer la mauvaise
        langue tout en rapportant un succès.
        """
        rid = self.language_name_resource_id
        return [
            f'//*[@resource-id="{rid}" and @text="{native_name}"]',
            f'//android.widget.TextView[@text="{native_name}"]',
        ]


SETTINGS_SELECTORS = SettingsSelectors()
