"""Selectors for the TikTok country picker flow."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L

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
    @property
    def screen_indicator(self) -> List[str]:
        return L("country_picker.screen_indicator")

    # Bouton fermer (croix en haut à gauche)
    # resource-id: com.zhiliaoapp.musically:id/be6  content-desc="Close"
    @property
    def close_button(self) -> List[str]:
        return L("country_picker.close_button")

    # Champ de recherche des pays
    # resource-id: com.zhiliaoapp.musically:id/tlr  hint="Search countries and regions"
    _search_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@resource-id, ":id/tlr")]',
    ])

    @property
    def search_input(self) -> List[str]:
        return self._search_input_base + L("country_picker.search_input")

    # Premier élément de la liste des pays (après filtrage par recherche)
    # resource-id: com.zhiliaoapp.musically:id/eqo  (LinearLayout cliquable)
    first_country_item: List[str] = field(default_factory=lambda: [
        '(//android.widget.LinearLayout[contains(@resource-id, ":id/eqo")])[1]',
        '(//android.widget.LinearLayout[.//android.widget.TextView[contains(@resource-id, ":id/z83")]])[1]',
    ])


COUNTRY_PICKER_SELECTORS = CountryPickerSelectors()
