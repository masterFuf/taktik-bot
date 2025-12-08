from typing import List, Set, Optional
from loguru import logger
from ..selectors import SCROLL_SELECTORS

class ScrollEndDetector:
    """
    Détecte la fin du scroll dans une liste (followers/following) en surveillant la répétition 
    des mêmes utilisateurs et la présence du bouton "Load More".
    Inspiré de la logique Insomniac pour une détection plus robuste.
    """
    def __init__(self, repeats_to_end=5, device=None):
        """
        Initialise le détecteur de fin de scroll.
        
        Args:
            repeats_to_end: Nombre de répétitions avant de considérer la fin atteinte
            device: Instance du device pour détecter les boutons "Load More"
        """
        self.repeats_to_end = repeats_to_end
        self.device = device
        self._repeat_count = 0
        self._last_seen = set()
        self._total_unique_users = 0
        self.pages = []
        
        # Nouvelles métriques pour l'optimisation
        self._consecutive_empty_pages = 0
        self._pages_without_new_users = 0
        self._last_page_hash = None
        self._duplicate_page_count = 0
        self.logger = logger.bind(module="scroll-end-detector")
        
        # Sélecteurs pour détecter le bouton "Load More" / "Voir plus" ou fin de liste
        # Utiliser les sélecteurs centralisés
        self.load_more_selectors = SCROLL_SELECTORS.load_more_selectors
        self.end_of_list_indicators = SCROLL_SELECTORS.end_of_list_indicators
    
    def _find_element_from_selectors(self, selectors: list, element_name: str) -> object:
        """Find first matching element from a list of xpath selectors."""
        if not self.device:
            return None
        for selector in selectors:
            try:
                element = self.device.xpath(selector)
                if element.exists:
                    self.logger.debug(f"{element_name} détecté: {selector}")
                    return element
            except Exception as e:
                self.logger.debug(f"Erreur lors de la vérification {element_name}: {e}")
        return None

    def notify_new_page(self, usernames: List[str], processed_usernames: Optional[List[str]] = None) -> bool:
        """
        Appelé à chaque nouvelle page (après un scroll), avec la liste des usernames visibles.
        
        Args:
            usernames: Liste des usernames visibles sur la page actuelle
            processed_usernames: Liste des usernames réellement traités (optionnel)
            
        Returns:
            bool: True si de nouveaux utilisateurs ont été détectés
        """
        if not usernames:
            self._consecutive_empty_pages += 1
            self.logger.debug(f"Page vide détectée ({self._consecutive_empty_pages} consécutives)")
            return False
            
        current_set = set(usernames)
        new_users = current_set - self._last_seen
        
        # Calculer un hash de la page pour détecter les doublons exacts
        page_hash = hash(tuple(sorted(usernames)))
        
        # Détecter les pages identiques consécutives
        if page_hash == self._last_page_hash:
            self._duplicate_page_count += 1
            self.logger.debug(f"Page identique détectée ({self._duplicate_page_count} fois consécutives)")
        else:
            self._duplicate_page_count = 0
            self._last_page_hash = page_hash
        
        # Vérifier s'il y a de nouveaux utilisateurs
        new_users = set(usernames) - self._last_seen
        
        # Compter les pages vides
        if len(usernames) == 0:
            self._consecutive_empty_pages += 1
        else:
            self._consecutive_empty_pages = 0
        
        if len(new_users) == 0:
            self._repeat_count += 1
            self._pages_without_new_users += 1
            self.logger.debug(f"Aucun nouvel utilisateur ({self._repeat_count}/{self.repeats_to_end}, {self._pages_without_new_users} pages sans nouveaux utilisateurs)")
        else:
            self._repeat_count = 0
            self._pages_without_new_users = 0
            self._total_unique_users += len(new_users)
            self._last_seen.update(new_users)
            
            # Si on a des utilisateurs traités, ne compter que ceux-là
            if processed_usernames is not None:
                actually_processed = len([u for u in new_users if u in processed_usernames])
                self.logger.debug(f"{len(new_users)} nouveaux utilisateurs détectés, {actually_processed} réellement traités (total: {self._total_unique_users})")
            else:
                self.logger.debug(f"{len(new_users)} nouveaux utilisateurs détectés (total: {self._total_unique_users})")
        
        self.pages.append(usernames)
        return len(new_users) > 0

    def has_load_more_button(self) -> bool:
        """Vérifie s'il y a un bouton "Load More" visible à l'écran."""
        return self._find_element_from_selectors(self.load_more_selectors, "Bouton 'Load More'") is not None
    
    def click_load_more_if_present(self) -> bool:
        """Clique sur le bouton "Load More" s'il est présent."""
        element = self._find_element_from_selectors(self.load_more_selectors, "Bouton 'Load More'")
        if element:
            self.logger.info("Clic sur le bouton 'Load More'")
            element.click()
            return True
        return False
    
    def has_end_of_list_indicator(self) -> bool:
        """Vérifie s'il y a un indicateur de fin de liste visible."""
        return self._find_element_from_selectors(self.end_of_list_indicators, "Indicateur de fin de liste") is not None

    def should_use_fast_scroll(self) -> bool:
        """
        Détermine si le scroll rapide doit être utilisé.
        
        Returns:
            bool: True si le scroll rapide est recommandé
        """
        # Conditions pour activer le scroll rapide
        fast_scroll_conditions = [
            self._repeat_count >= 3,  # Condition originale
            self._pages_without_new_users >= 5,  # 5 pages sans nouveaux utilisateurs
            self._duplicate_page_count >= 2,  # 2 pages identiques consécutives
            self._consecutive_empty_pages >= 3  # 3 pages vides consécutives
        ]
        
        return any(fast_scroll_conditions)

    def is_the_end(self) -> bool:
        """
        Détermine si la fin de la liste a été atteinte.
        
        Returns:
            bool: True si la fin est atteinte
        """
        # Conditions multiples pour détecter la fin plus rapidement
        conditions = [
            self._repeat_count >= self.repeats_to_end,  # Condition originale
            self._consecutive_empty_pages >= 8,  # 8 pages vides consécutives
            self._duplicate_page_count >= 5,  # 5 pages identiques consécutives
            self._pages_without_new_users >= 15  # 15 pages sans nouveaux utilisateurs
        ]
        
        if any(conditions):
            reason = ""
            if self._repeat_count >= self.repeats_to_end:
                reason = f"répétitions ({self._repeat_count}/{self.repeats_to_end})"
            elif self._consecutive_empty_pages >= 8:
                reason = f"pages vides consécutives ({self._consecutive_empty_pages})"
            elif self._duplicate_page_count >= 5:
                reason = f"pages identiques consécutives ({self._duplicate_page_count})"
            elif self._pages_without_new_users >= 15:
                reason = f"pages sans nouveaux utilisateurs ({self._pages_without_new_users})"
            
            self.logger.info(f"Fin détectée par: {reason}")
            return True
            
        return False

    def get_stats(self) -> dict:
        """
        Retourne les statistiques du détecteur.
        
        Returns:
            dict: Statistiques de détection
        """
        return {
            'total_pages': len(self.pages),
            'total_unique_users': self._total_unique_users,
            'repeat_count': self._repeat_count,
            'consecutive_empty_pages': self._consecutive_empty_pages,
            'is_end': self.is_the_end()
        }

    def reset(self):
        """Remet à zéro tous les compteurs et historiques."""
        self.pages.clear()
        self._last_seen.clear()
        self._repeat_count = 0
        self._consecutive_empty_pages = 0
        self._total_unique_users = 0
        self.logger.debug("ScrollEndDetector réinitialisé")
