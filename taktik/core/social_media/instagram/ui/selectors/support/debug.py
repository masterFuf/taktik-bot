from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class DebugSelectors:
    """Sélecteurs pour le debug et l'analyse de l'interface."""
    
    # === Éléments génériques ===
    clickable_elements: str = '//*[@clickable="true"]'
    image_views: str = '//android.widget.ImageView'
    recycler_views: str = '//androidx.recyclerview.widget.RecyclerView'
    image_buttons: str = '//*[contains(@resource-id, "image_button")]'

DEBUG_SELECTORS = DebugSelectors()
