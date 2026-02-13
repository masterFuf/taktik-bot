from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class FollowersListSelectors:
    """Sélecteurs pour la détection et navigation dans la liste followers/following."""
    
    # === Détection liste followers (éléments UNIQUES à cette vue) ===
    list_indicators: List[str] = field(default_factory=lambda: [
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_view_pager"]',
        '//android.widget.Button[contains(@text, "mutual")]',
    ])

FOLLOWERS_LIST_SELECTORS = FollowersListSelectors()
