from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class FollowersListSelectors:
    """Selectors for detecting and navigating the followers/following list."""
    
    # === Followers-list detection (nodes UNIQUE to this view) ===
    list_indicators: List[str] = field(default_factory=lambda: [
        # Tab bar at the top of the list. WARNING: it SCROLLS off screen as soon as the
        # list moves, so on its own it cannot detect an already-scrolled list.
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        # Follower rows: present as long as we are on the list, scrolled or not. Without
        # them, coming back into a scrolled list read as "not on the list", triggering a
        # re-navigation from the top and a false loop detection that cut the session short.
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        # Supprimés 2026-03-07: view_pager (0/15), mutual (0/15)
    ])

FOLLOWERS_LIST_SELECTORS = FollowersListSelectors()
