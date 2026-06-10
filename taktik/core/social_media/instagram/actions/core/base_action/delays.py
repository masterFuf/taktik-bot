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
        """Délai humanisé selon le type d'action — micro-hésitations seulement.

        Le bot est déjà lent du fait du travail réel (navigation, analyse IA ~2,5s, scroll), donc
        les pauses d'OBSERVATION (lire la bio, regarder le profil, satisfaction après like) sont
        redondantes et lisaient robotiques empilées par-dessus. On garde de vraies micro-hésitations
        (< ~1s) ; seuls les délais FONCTIONNELS (regarder une story = vrai contenu, temps de
        chargement IG) restent plus longs. (Décision Kevin 2026-06-10, cf. retrait du rythme.)"""
        delays = {
            'click': (0.15, 0.4),
            'navigation': (0.3, 0.8),
            'scroll': (0.2, 0.5),
            'typing': (0.08, 0.15),
            'reading_bio': (0.4, 1.2),      # l'analyse IA fournit déjà le temps de "lecture"
            'before_like': (0.2, 0.7),      # courte hésitation avant like
            'after_like': (0.3, 0.9),       # courte hésitation après like
            'before_follow': (0.3, 1.0),    # courte hésitation avant follow
            'story_view': (1.5, 4.0),       # FONCTIONNEL : on regarde vraiment la story
            'story_load': (0.8, 1.5),       # FONCTIONNEL : chargement story
            'load_more': (1.2, 2.2),        # FONCTIONNEL : Instagram doit charger plus
            'profile_view': (0.4, 1.0),     # l'analyse IA couvre déjà l'observation du profil
            'default': (0.2, 0.6)
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
