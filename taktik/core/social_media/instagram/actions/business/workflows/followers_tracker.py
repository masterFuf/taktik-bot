"""Tracker pour diagnostiquer les problèmes de navigation dans la liste des followers."""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional


class FollowersTracker:
    """
    Enregistre les mouvements dans la liste des followers pour diagnostiquer:
    - Les retours en début de liste (boucles infinies)
    - Les revisites de profils déjà filtrés
    - Les problèmes de scroll
    """
    
    def __init__(self, account_username: str, target_username: str):
        self.account_username = account_username
        self.target_username = target_username
        self.session_start = datetime.now()
        
        # Créer le dossier de logs dans AppData pour éviter les problèmes de permission
        app_data = os.environ.get('APPDATA', os.path.expanduser('~'))
        self.log_dir = Path(app_data) / 'taktik-desktop' / 'logs' / 'followers_tracking'
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Fichier de log pour cette session
        timestamp = self.session_start.strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{account_username}_{target_username}_{timestamp}.jsonl"
        
        # État interne pour détecter les anomalies
        self.visited_usernames: List[str] = []  # Ordre de visite
        self.visible_history: List[List[str]] = []  # Historique des listes visibles (pages)
        self.scroll_count = 0
        self.loop_detected_count = 0
        self.repeats_to_end = 5  # Nombre de pages identiques pour détecter la fin (augmenté pour éviter faux positifs)
        self.first_page_usernames: List[str] = []  # Première page vue (pour détecter retour au début)
        
        # Écrire l'en-tête de session
        self._log_event("session_start", {
            "account": account_username,
            "target": target_username,
            "timestamp": self.session_start.isoformat()
        })
    
    def _log_event(self, event_type: str, data: Dict[str, Any]):
        """Écrit un événement dans le fichier de log."""
        entry = {
            "time": datetime.now().strftime("%H:%M:%S.%f")[:-3],
            "elapsed_s": (datetime.now() - self.session_start).total_seconds(),
            "event": event_type,
            **data
        }
        
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    def log_visible_followers(self, visible_usernames: List[str], after_action: str = "scan"):
        """
        Enregistre la liste des followers visibles à l'écran.
        Détecte si on est revenu en début de liste (style Insomniac).
        
        Returns:
            bool: True si une boucle (retour au début) est détectée
        """
        # Stocker la première page pour référence
        if not self.first_page_usernames and visible_usernames:
            self.first_page_usernames = visible_usernames.copy()
        
        self.visible_history.append(visible_usernames.copy())
        
        # === DÉTECTION DE BOUCLE (style Insomniac) ===
        loop_detected = False
        is_same_as_previous = False
        consecutive_same_pages = 0
        
        if len(self.visible_history) >= 2:
            # Vérifier si la page actuelle est identique à la précédente
            prev_page = self.visible_history[-2]
            is_same_as_previous = visible_usernames == prev_page
            
            # Compter les pages consécutives identiques
            if is_same_as_previous:
                for i in range(len(self.visible_history) - 1, 0, -1):
                    if self.visible_history[i] == self.visible_history[i-1]:
                        consecutive_same_pages += 1
                    else:
                        break
        
        # Détecter un retour en début de liste
        if len(self.visible_history) > 5 and visible_usernames and self.first_page_usernames:
            # Comparer avec la première page
            # Si au moins 2 des 3 premiers usernames sont les mêmes → retour au début
            common_with_first = sum(1 for a, b in zip(visible_usernames[:3], self.first_page_usernames[:3]) if a == b)
            if common_with_first >= 2:
                loop_detected = True
                self.loop_detected_count += 1
        
        self._log_event("visible_followers", {
            "action": after_action,
            "count": len(visible_usernames),
            "usernames": visible_usernames[:10],  # Max 10 pour lisibilité
            "scroll_count": self.scroll_count,
            "loop_detected": loop_detected,
            "is_same_as_previous": is_same_as_previous,
            "consecutive_same_pages": consecutive_same_pages,
            "history_size": len(self.visible_history)
        })
        
        if loop_detected:
            self._log_event("WARNING_LOOP_DETECTED", {
                "message": "Retour en début de liste détecté!",
                "first_page": self.first_page_usernames[:5],
                "current_page": visible_usernames[:5],
                "total_loops": self.loop_detected_count
            })
        
        return loop_detected
    
    def is_end_of_list(self) -> bool:
        """
        Détecte si on a atteint la fin de la liste (style Insomniac).
        Retourne True si les N dernières pages sont identiques ET qu'on a fait assez de scrolls.
        
        Conditions pour éviter les faux positifs:
        - Au moins 10 scrolls effectués
        - Au moins 50 usernames vus
        - Les N dernières pages sont identiques
        """
        # Éviter les faux positifs en début de session
        if self.scroll_count < 10:
            return False
        
        # Compter les usernames uniques vus dans l'historique
        all_seen_usernames = set()
        for page in self.visible_history:
            all_seen_usernames.update(page)
        
        if len(all_seen_usernames) < 50:
            return False
        
        if len(self.visible_history) < self.repeats_to_end:
            return False
        
        last_page = self.visible_history[-1]
        for i in range(2, self.repeats_to_end + 1):
            if self.visible_history[-i] != last_page:
                return False
        
        self._log_event("END_OF_LIST_DETECTED", {
            "message": f"Mêmes followers vus {self.repeats_to_end} fois consécutives après {self.scroll_count} scrolls",
            "last_page": last_page[:5],
            "total_visited": len(self.visited_usernames),
            "scroll_count": self.scroll_count
        })
        return True
    
    def check_position_after_back(self, expected_username: str, visible_usernames: List[str]) -> bool:
        """
        Vérifie si on est revenu à la bonne position après un back().
        
        Args:
            expected_username: Le username qu'on s'attend à voir (dernier visité ou suivant)
            visible_usernames: Liste des usernames actuellement visibles
            
        Returns:
            bool: True si la position est correcte
        """
        position_ok = expected_username in visible_usernames
        
        self._log_event("position_check_after_back", {
            "expected": expected_username,
            "found": position_ok,
            "visible_sample": visible_usernames[:5]
        })
        
        if not position_ok:
            self._log_event("WARNING_POSITION_LOST", {
                "message": f"Position perdue! @{expected_username} n'est plus visible",
                "visible": visible_usernames[:5]
            })
        
        return position_ok
    
    def log_scroll(self, direction: str = "down"):
        """Enregistre un scroll."""
        self.scroll_count += 1
        self._log_event("scroll", {
            "direction": direction,
            "scroll_number": self.scroll_count
        })
    
    def log_profile_visit(self, username: str, position_in_list: int, 
                          already_in_db: bool = False, filter_reason: Optional[str] = None):
        """
        Enregistre une visite de profil.
        """
        is_revisit = username in self.visited_usernames
        visit_number = self.visited_usernames.count(username) + 1
        
        self.visited_usernames.append(username)
        
        self._log_event("profile_visit", {
            "username": username,
            "position": position_in_list,
            "visit_number": visit_number,
            "is_revisit": is_revisit,
            "already_in_db": already_in_db,
            "total_visited": len(set(self.visited_usernames))
        })
        
        if is_revisit:
            self._log_event("WARNING_REVISIT", {
                "message": f"Profil @{username} déjà visité cette session!",
                "previous_visits": visit_number - 1
            })
    
    def log_profile_filtered(self, username: str, reason: str, profile_data: Dict[str, Any]):
        """Enregistre un profil filtré avec ses données."""
        self._log_event("profile_filtered", {
            "username": username,
            "reason": reason,
            "posts": profile_data.get("posts_count", 0),
            "followers": profile_data.get("followers_count", 0),
            "following": profile_data.get("following_count", 0),
            "is_private": profile_data.get("is_private", False)
        })
    
    def log_profile_interacted(self, username: str, actions: Dict[str, bool]):
        """Enregistre une interaction réussie."""
        self._log_event("profile_interacted", {
            "username": username,
            "liked": actions.get("liked", False),
            "followed": actions.get("followed", False),
            "story_viewed": actions.get("story_viewed", False),
            "commented": actions.get("commented", False)
        })
    
    def log_skipped_from_db(self, username: str, reason: str):
        """Enregistre un profil skippé car déjà en DB."""
        self._log_event("skipped_from_db", {
            "username": username,
            "reason": reason
        })
    
    def log_recovery_attempt(self, reason: str, success: bool):
        """Enregistre une tentative de récupération de navigation."""
        self._log_event("recovery_attempt", {
            "reason": reason,
            "success": success
        })
    
    def log_position_check(self, last_visited: str, next_expected: str, 
                           visible_usernames: List[str], position_ok: bool):
        """Enregistre une vérification de position après retour de profil."""
        self._log_event("position_check", {
            "last_visited": last_visited,
            "next_expected": next_expected,
            "visible_sample": visible_usernames[:5],
            "position_ok": position_ok
        })
    
    def log_session_end(self, stats: Dict[str, Any]):
        """Enregistre la fin de session avec les stats."""
        self._log_event("session_end", {
            "duration_s": (datetime.now() - self.session_start).total_seconds(),
            "total_scrolls": self.scroll_count,
            "unique_visited": len(set(self.visited_usernames)),
            "total_visits": len(self.visited_usernames),
            "loops_detected": self.loop_detected_count,
            "stats": stats
        })
        
        # Générer un résumé si des problèmes ont été détectés
        if self.loop_detected_count > 0:
            self._log_event("SUMMARY_ISSUES", {
                "loops_detected": self.loop_detected_count,
                "message": "Des boucles ont été détectées - vérifier les logs pour plus de détails"
            })
    
    def get_log_file_path(self) -> str:
        """Retourne le chemin du fichier de log."""
        return str(self.log_file)
