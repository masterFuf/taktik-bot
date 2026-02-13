"""Sélecteurs UI pour le scroll et le chargement TikTok."""

from typing import List
from dataclasses import dataclass, field


@dataclass
class ScrollSelectors:
    """Sélecteurs pour le scroll et le chargement TikTok."""
    
    loading_indicator: List[str] = field(default_factory=lambda: [
        '//android.widget.ProgressBar',
        '//android.view.View[contains(@content-desc, "Loading")]'
    ])
    
    end_of_list: List[str] = field(default_factory=lambda: [
        '//android.widget.TextView[contains(@text, "No more")]',
        '//android.widget.TextView[contains(@text, "Plus de")]'
    ])


SCROLL_SELECTORS = ScrollSelectors()
