from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

from ..locales import L

@dataclass
class ScrollSelectors:
    """Selectors for end-of-scroll detection and loading elements."""

    # === Indicateurs de chargement ===
    # Consolidated: //* covers every element type.
    # Language-dependent (locales overlay): every fragment carries localized text or
    # content-desc, so there is no neutral base field.
    @property
    def load_more_selectors(self) -> List[str]:
        return L("scroll.load_more_selectors")

    # === End-of-list markers ===
    # Consolidated: exact and contains forms merged.
    _end_of_list_indicators_base: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',
    ])

    @property
    def end_of_list_indicators(self) -> List[str]:
        # Base neutre (resource-id) puis fragments localises (text).
        return self._end_of_list_indicators_base + L("scroll.end_of_list_indicators")

SCROLL_SELECTORS = ScrollSelectors()
