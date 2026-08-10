"""Humanized delays — gaussian distribution, fatigue-aware, action-type based."""

import time


class DelaysMixin:
    """Mixin: délais humanisés (_random_sleep, _human_like_delay, _maybe_take_break)."""

    def _random_sleep(self, min_delay: float = 0.3, max_delay: float = 0.8,
                      scale: float = 1.0) -> None:
        """Sleep on a gaussian distribution, with the session fatigue applied."""
        bounded_scale = min(1.60, max(0.60, float(scale)))
        delay = self.human.gaussian_delay(min_delay, max_delay) * bounded_scale
        self.logger.debug(f"⏱️ Random sleep: {delay:.2f}s (fatigue: x{self.human.get_fatigue_multiplier():.2f})")
        time.sleep(delay)
    
    def _human_like_delay(self, action_type: str = 'general', scale: float = 1.0) -> None:
        """Humanized delay per action type — micro-hesitations only.

        The bot is already slow from the real work it does, so the OBSERVATION pauses —
        reading a bio, looking at a profile, dwelling after a like — were redundant and read
        as robotic stacked on top. Real micro-hesitations are kept; only the FUNCTIONAL
        delays — watching a story, which is real content, or waiting for a load — stay
        longer."""
        delays = {
            'click': (0.15, 0.4),
            'navigation': (0.3, 0.8),
            'scroll': (0.2, 0.5),
            'typing': (0.08, 0.15),
            'reading_bio': (0.4, 1.2),      # the qualification already provides the reading time
            'before_like': (0.2, 0.7),      # courte hésitation avant like
            'after_like': (0.3, 0.9),       # courte hésitation après like
            'before_follow': (0.3, 1.0),    # courte hésitation avant follow
            'story_view': (1.5, 4.0),       # FONCTIONNEL : on regarde vraiment la story
            'story_load': (0.8, 1.5),       # FONCTIONNEL : chargement story
            'story_transition': (0.2, 0.6), # a beat after the tap, before checking the viewer
            'load_more': (1.2, 2.2),        # FUNCTIONAL: the app needs longer to load
            'profile_view': (0.4, 1.0),     # the qualification already covers looking at the profile
            'default': (0.2, 0.6)
        }

        min_delay, max_delay = delays.get(action_type, delays['default'])
        self._random_sleep(min_delay, max_delay, scale=scale)
        
        # Record the action for the break system
        self.human.record_action()
    
    def _maybe_take_break(self) -> bool:
        """Check and take a break when needed. True when one was taken."""
        should_break, break_type, duration = self.human.should_take_break()
        
        if should_break:
            if break_type == 'long':
                self.logger.info(f"☕ Pause longue naturelle ({duration/60:.1f} min) - {self.human.interactions_count} interactions effectuées")
            else:
                self.logger.info(f"⏸️ Pause courte ({duration:.0f}s) - {self.human.interactions_count} interactions")
            
            time.sleep(duration)
            return True
        
        return False
