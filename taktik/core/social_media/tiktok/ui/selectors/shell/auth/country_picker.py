"""Selectors for the TikTok country picker flow."""

from typing import List
from dataclasses import dataclass, field

from ...locales import L

# ---------------------------------------------------------------------------
# Country picker selectors
# ---------------------------------------------------------------------------

@dataclass
class CountryPickerSelectors:
    """Selectors for the country/region picker screen.

    Dump observé : ui_dump_20260502_141800.xml
    Appears when the country-code button is tapped in the phone tab of the
    signup screen.

    Éléments clés :
      - Titre           : id=title  text="Select country/region"
      - close button
      - Champ recherche : id=tlr    hint="Search countries and regions"  (EditText)
      - country list
        - one row
          - Nom pays    : id=z83    (TextView)
          - Code phone  : id=ynw    (TextView, ex: "+33")
    """

    # Indicateur de l'écran
    # resource-id: com.zhiliaoapp.musically:id/title  text="Select country/region"
    @property
    def screen_indicator(self) -> List[str]:
        return L("country_picker.screen_indicator")

    # Close button, at the top left
    # resource-id: com.zhiliaoapp.musically:id/be6  content-desc="Close"
    @property
    def close_button(self) -> List[str]:
        return L("country_picker.close_button")

    # Country search field
    # resource-id: com.zhiliaoapp.musically:id/tlr  hint="Search countries and regions"
    _search_input_base: List[str] = field(default_factory=lambda: [
        '//android.widget.EditText[contains(@resource-id, ":id/tlr")]',
    ])

    @property
    def search_input(self) -> List[str]:
        return self._search_input_base + L("country_picker.search_input")

    # First item of the country list, once filtered by the search
    # resource-id: com.zhiliaoapp.musically:id/eqo  (LinearLayout cliquable)
    first_country_item: List[str] = field(default_factory=lambda: [
        '(//android.widget.LinearLayout[contains(@resource-id, ":id/eqo")])[1]',
        '(//android.widget.LinearLayout[.//android.widget.TextView[contains(@resource-id, ":id/z83")]])[1]',
    ])


COUNTRY_PICKER_SELECTORS = CountryPickerSelectors()
