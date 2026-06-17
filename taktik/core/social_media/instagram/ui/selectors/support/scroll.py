from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class ScrollSelectors:
    """Sélecteurs pour la détection de fin de scroll et éléments de chargement."""

    # === Indicateurs de chargement ===
    # Consolidé 2026-03-07: 12 → 5 sélecteurs (//* couvre tous les types d'éléments)
    # Langue-dependant (overlay locales/) : tous les fragments portent du @text /
    # @content-desc FR/EN -> aucun champ base neutre.
    @property
    def load_more_selectors(self) -> List[str]:
        return L("scroll.load_more_selectors")

    # === Indicateurs de fin de liste ===
    # Consolidé 2026-03-07: 6 → 4 sélecteurs (merge exact @text avec contains)
    _end_of_list_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',
    ])

    @property
    def end_of_list_indicators(self) -> List[str]:
        # Base neutre (resource-id) puis fragments localises (text).
        return self._end_of_list_indicators_base + L("scroll.end_of_list_indicators")

SCROLL_SELECTORS = ScrollSelectors()
