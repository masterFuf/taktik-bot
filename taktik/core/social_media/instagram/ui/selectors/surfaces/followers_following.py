from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field

@dataclass
class FollowersListSelectors:
    """Sélecteurs pour la détection et navigation dans la liste followers/following."""
    
    # === Détection liste followers (éléments UNIQUES à cette vue) ===
    list_indicators: List[str] = field(default_factory=lambda: [
        # Barre d'onglets Followers|Suivis (haut de liste). ATTENTION: elle DÉFILE hors écran
        # dès qu'on scrolle, donc seule elle ne suffit pas pour détecter une liste déjà scrollée.
        '//*[@resource-id="com.instagram.android:id/unified_follow_list_tab_layout"]',
        # Lignes de followers : présentes tant qu'on est sur la liste, scrollée ou non. Sans ça,
        # un retour-back dans une liste scrollée était vu comme "pas sur la liste" → re-navigation
        # depuis le haut → fausse "LOOP DETECTED" → session coupée tôt (logs device 2026-06-26).
        '//*[@resource-id="com.instagram.android:id/follow_list_username"]',
        # Supprimés 2026-03-07: view_pager (0/15), mutual (0/15) — voir SELECTOR_CLEANUP_BACKUP_2026-03-07.md
    ])

FOLLOWERS_LIST_SELECTORS = FollowersListSelectors()
