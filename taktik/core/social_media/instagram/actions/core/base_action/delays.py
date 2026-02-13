"""Humanized delays — gaussian distribution, fatigue-aware, action-type based."""

import time


class DelaysMixin:
    """Mixin: délais humanisés (_random_sleep, _human_like_delay, _maybe_take_break)."""

    def _random_sleep(self, min_delay: float = 0.3, max_delay: float = 0.8) -> None:
        """Sleep avec distribution gaussienne et fatigue de session."""
        delay = self.human.gaussian_delay(min_delay, max_delay)
        self.logger.debug(f"⏱️ Random sleep: {delay:.2f}s (fatigue: x{self.human.get_fatigue_multiplier():.2f})")
        time.sleep(delay)
    
    def _human_like_delay(self, action_type: str = 'general') -> None:
        """Délai humanisé selon le type d'action avec distribution gaussienne."""
        delays = {
            'click': (0.2, 0.5),
            'navigation': (0.7, 1.5),
            'scroll': (0.3, 0.7),
            'typing': (0.08, 0.15),
            'reading_bio': (2.0, 5.0),      # Temps de lecture réaliste
            'before_like': (0.5, 2.0),      # Hésitation avant like
            'after_like': (1.0, 3.0),       # Satisfaction après like
            'before_follow': (1.0, 3.0),    # Réflexion avant follow
            'story_view': (2.0, 5.0),       # Regarder une story
            'story_load': (1.0, 2.0),       # Chargement story
            'load_more': (2.0, 4.0),        # Après clic load more (Instagram needs time to load)
            'profile_view': (1.5, 4.0),     # Observer un profil
            'default': (0.3, 0.8)
        }
        
        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay)
        
        # Enregistrer l'action pour le système de pauses
        self.human.record_action()
    
    def _maybe_take_break(self) -> bool:
        """Vérifie et prend une pause si nécessaire. Retourne True si pause prise."""
        should_break, break_type, duration = self.human.should_take_break()
        
        if should_break:
            if break_type == 'long':
                self.logger.info(f"☕ Pause longue naturelle ({duration/60:.1f} min) - {self.human.interactions_count} interactions effectuées")
            else:
                self.logger.info(f"⏸️ Pause courte ({duration:.0f}s) - {self.human.interactions_count} interactions")
            
            time.sleep(duration)
            return True
        
        return False
