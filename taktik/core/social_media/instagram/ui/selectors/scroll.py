from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass 
class ScrollSelectors:
    """Sélecteurs pour la détection de fin de scroll et éléments de chargement."""
    
    # === Indicateurs de chargement ===
    load_more_selectors: List[str] = field(default_factory=lambda: [
        # Sélecteurs français (Instagram France)
        "//android.widget.TextView[contains(@text, 'Voir plus')]",
        "//android.widget.Button[contains(@text, 'Voir plus')]",
        "//*[contains(@content-desc, 'Voir plus')]",
        "//android.widget.TextView[contains(@text, 'voir plus')]",
        # Sélecteurs anglais (Instagram international)
        "//android.widget.TextView[contains(@text, 'See more')]",
        "//android.widget.Button[contains(@text, 'See more')]",
        "//*[contains(@content-desc, 'See more')]",
        "//android.widget.TextView[contains(@text, 'see more')]",
        # Sélecteurs génériques (fallback)
        '//*[@text="Load more" or @text="Show more" or @text="See more"]',
        '//*[contains(@text, "Load") and contains(@text, "more")]',
        '//*[@content-desc="Load more" or @content-desc="Show more"]',
        '//android.widget.Button[contains(@text, "more")]'
    ])
    
    # === Indicateurs de fin de liste ===
    end_of_list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',  # Bouton "See all suggestions" = fin de liste followers
        '//*[@text="See all suggestions"]',
        '//*[contains(@text, "See all suggestions")]',
        '//*[@text="You\'re all caught up" or @text="No more suggestions"]',
        '//*[contains(@text, "caught up") or contains(@text, "End of list")]',
        '//*[contains(@text, "No more") or contains(@text, "That\'s all")]'
    ])

SCROLL_SELECTORS = ScrollSelectors()
