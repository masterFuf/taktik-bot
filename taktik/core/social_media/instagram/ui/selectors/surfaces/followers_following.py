from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class FollowersListSelectors:
    """Sélecteurs pour la détection et navigation dans la liste followers/following."""
    
    # === Détection liste followers (éléments UNIQUES à cette vue) ===
    list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        # Supprimés 2026-03-07: view_pager (0/15), mutual (0/15) — voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md
    ])

FOLLOWERS_LIST_SELECTORS = FollowersListSelectors()
