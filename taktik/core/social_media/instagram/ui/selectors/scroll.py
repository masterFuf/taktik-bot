from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass 
class ScrollSelectors:
    """Sélecteurs pour la détection de fin de scroll et éléments de chargement."""
    
    # === Indicateurs de chargement ===
    # Consolidé 2026-03-07: 12 → 5 sélecteurs (//* couvre tous les types d'éléments)
    load_more_selectors: List[str] = field(default_factory=lambda: [
        # FR: "Voir plus" (couvre TextView, Button, tout élément)
        '//*[contains(@text, "Voir plus") or contains(@text, "voir plus")]',
        # EN: "See more" (couvre TextView, Button, tout élément)
        '//*[contains(@text, "See more") or contains(@text, "see more")]',
        # content-desc fallback (FR + EN)
        '//*[contains(@content-desc, "Voir plus") or contains(@content-desc, "See more")]',
        # Generics: "Load more", "Show more"
        '//*[contains(@text, "Load more") or contains(@text, "Show more")]',
        # content-desc generics
        '//*[@content-desc="Load more" or @content-desc="Show more"]',
    ])
    
    # === Indicateurs de fin de liste ===
    # Consolidé 2026-03-07: 6 → 4 sélecteurs (merge exact @text avec contains)
    end_of_list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/see_all_button"]',
        '//*[contains(@text, "See all suggestions") or contains(@text, "Voir toutes les suggestions")]',
        '//*[contains(@text, "caught up") or contains(@text, "No more suggestions") or contains(@text, "End of list")]',
        '//*[contains(@text, "No more") or contains(@text, "That\'s all") or contains(@text, "Aucun autre")]',
    ])

SCROLL_SELECTORS = ScrollSelectors()
