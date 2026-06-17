"""Sélecteurs UI pour le scroll et le chargement TikTok."""

from typing import List
from dataclasses import dataclass, field

from ..locales import L


@dataclass
class ScrollSelectors:
    """Sélecteurs pour le scroll et le chargement TikTok."""

    loading_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.ProgressBar',
        '//android.view.View[contains(@content-desc, "Loading")]'
    ])

    @property
    def end_of_list(self) -> List[str]:
        return L("scroll.end_of_list")


SCROLL_SELECTORS = ScrollSelectors()
