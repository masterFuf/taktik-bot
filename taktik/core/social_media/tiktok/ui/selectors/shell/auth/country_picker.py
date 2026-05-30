"""Selectors for the TikTok country picker flow."""

from typing import List
from dataclasses import dataclass, field

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
