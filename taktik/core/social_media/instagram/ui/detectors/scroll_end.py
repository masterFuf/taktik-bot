from typing import List, Set, Optional
from loguru import logger
from ..selectors import SCROLL_SELECTORS

class ScrollEndDetector:
    """
    Detects the end of a list scroll by watching the repetition of the same
    usernames and the presence of a "load more" button.
    
    """
    def __init__(self, repeats_to_end=5, device=None):
        """
        Initialise the end-of-scroll detector.
        
        Args:
                repeats_to_end: repetitions before the end is considered reached
                device: device instance, used to detect the "load more" button
        """
        self.repeats_to_end = repeats_to_end
        self.device = device
        self._repeat_count = 0
        self._last_seen = set()
        self._total_unique_users = 0
        self.pages = []
        
        # Metrics used for the optimization
        self._consecutive_empty_pages = 0
        self._pages_without_new_users = 0
        self._last_page_hash = None
        self._duplicate_page_count = 0
        self.logger = logger.bind(module="scroll-end-detector")
        
        # Selectors detecting the "load more" button or the end of the list
        # Use the centralized selectors
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
        Called on every new page, after a scroll, with the visible usernames.
        
        Args:
                usernames: usernames visible on the current page
                processed_usernames: usernames actually handled (optional)
            
        Returns:
            bool: True si de nouveaux utilisateurs ont été détectés
        """
        if not usernames:
            self._consecutive_empty_pages += 1
            self.logger.debug(f"Page vide détectée ({self._consecutive_empty_pages} consécutives)")
            return False
            
        current_set = set(usernames)
        new_users = current_set - self._last_seen
        
        # Hash the page to detect exact duplicates
        page_hash = hash(tuple(sorted(usernames)))
        
        # Detect consecutive identical pages
        if page_hash == self._last_page_hash:
            self._duplicate_page_count += 1
            self.logger.debug(f"Page identique détectée ({self._duplicate_page_count} fois consécutives)")
        else:
            self._duplicate_page_count = 0
            self._last_page_hash = page_hash
        
        # Vérifier s'il y a de nouveaux utilisateurs
        new_users = set(usernames) - self._last_seen
        
        # Count the empty pages
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
            
            # With handled users known, count only those
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
        """Tap the "load more" button when present."""
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
        Should the fast scroll be used?
        
        Returns:
                bool: True when the fast scroll is advisable
        """
        # Conditions enabling the fast scroll
        fast_scroll_conditions = [
            self._repeat_count >= 3,  # Condition originale
            self._pages_without_new_users >= 5,  # pages with no new user
            self._duplicate_page_count >= 2,  # 2 pages identiques consécutives
            self._consecutive_empty_pages >= 3  # 3 pages vides consécutives
        ]
        
        return any(fast_scroll_conditions)

    def is_the_end(self) -> bool:
        """Whether the END of the list has TRULY been reached.

        End-of-list is detected ONLY by signals that mean the list genuinely cannot advance any
        further: an empty screen several times, or the EXACT same page rendered identically several
        times in a row (the scroll no longer reveals anything = stuck at the bottom).

        We deliberately do NOT stop on "no NEW username for N scrolls" anymore (the former
        `_repeat_count`/`_pages_without_new_users` conditions): a small scroll, an overlap, or the
        list resumed after interacting with a profile can legitimately show no session-new username
        without being the end — that produced FALSE end-of-list detections (sessions stopping after
        a handful of profiles). Whether we have run out of followers WORTH interacting with is
        decided separately by `max_consecutive_known_usernames` in the workflow loop (keep scrolling
        while we still discover followers; stop only on a long run of already-interacted ones), with
        the loop's `max_scroll_attempts` as a hard backstop.
        """
        conditions = [
            self._consecutive_empty_pages >= 8,   # empty screen repeatedly -> nothing left to load
            self._duplicate_page_count >= 5,       # exact same page repeated -> scroll is stuck
        ]

        if any(conditions):
            if self._consecutive_empty_pages >= 8:
                reason = f"pages vides consécutives ({self._consecutive_empty_pages})"
            else:
                reason = f"pages identiques consécutives ({self._duplicate_page_count})"
            self.logger.info(f"Fin de liste réelle détectée par: {reason}")
            return True

        return False

    def get_stats(self) -> dict:
        """
        Detector statistics.
        
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
        """Reset every counter and history."""
        self.pages.clear()
        self._last_seen.clear()
        self._repeat_count = 0
        self._consecutive_empty_pages = 0
        self._total_unique_users = 0
        self.logger.debug("ScrollEndDetector réinitialisé")
