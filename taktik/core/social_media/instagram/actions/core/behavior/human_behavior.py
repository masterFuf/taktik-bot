"""Human behavior simulation — fatigue, breaks, right-skewed delays, random offsets."""

import time
import random
from typing import Tuple

from taktik.core.shared.behavior.sampling import lognormal_with_mean

# Breaks come after a number of REAL interactions and last a number of seconds. The means are the
# ones of the historical uniform draws (8-15 and 30-50 interactions, 5-15 s and 60-180 s); the laws
# are log-normal, wider, and scaled per session, so the rhythm is no longer the same narrow band
# in every run. Bounds are wide sanity limits: truncation redraws, and the mean is solved for them.
_SHORT_BREAK_EVERY = (11.5, 4, 28)       # (mean, min, max) interactions
_LONG_BREAK_EVERY = (40.0, 30, 160)
_BREAK_EVERY_CV = 0.35
_SHORT_BREAK_S = (10.0, 3.0, 60.0)       # (mean, min, max) seconds
_LONG_BREAK_S = (120.0, 30.0, 600.0)
_BREAK_LENGTH_CV = 0.5
# One session breaks more often, or longer, than another. Mean 1, so the long-run averages hold.
_SESSION_TEMPO = (1.0, 0.18, 0.6, 1.6)   # (mean, cv, min, max)
# Micro-delays: spread of the log-normal relative to the historical gaussian (sd = range / 4).
_DELAY_SPREAD_GAIN = 1.5


def _session_tempo() -> float:
    mean, cv, lo, hi = _SESSION_TEMPO
    return lognormal_with_mean(mean, cv, lo, hi)


class HumanBehavior:
    """Reproduce a realistic human rhythm."""
    
    # Singleton, so the state is shared across the actions
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.reset_session()
        
    def reset_session(self):
        """Reset for a new session: counters, and the session's own break rhythm."""
        self.session_start = time.time()
        self.actions_count = 0  # Every action, for the fatigue
        self.interactions_count = 0  # Real interactions only
        self.last_action_time = time.time()
        self.last_break_at = 0
        self.break_spacing_tempo = _session_tempo()
        self.break_length_tempo = _session_tempo()
        
        # Break configuration, based on the REAL interactions only
        self.interactions_before_short_break = self._break_every(_SHORT_BREAK_EVERY)
        self.interactions_before_long_break = self._break_every(_LONG_BREAK_EVERY, scaled=False)
        
    def _break_every(self, spec, scaled: bool = True) -> int:
        """Interactions until the next break of this kind, for this session's tempo.

        The long spacing is not scaled: a fast session would bring it under the short one's
        maximum, and the long break would start firing (see `should_take_break`)."""
        mean, lo, hi = spec
        tempo = self.break_spacing_tempo if scaled else 1.0
        return int(round(lognormal_with_mean(mean * tempo, _BREAK_EVERY_CV, lo, hi)))

    def _break_length(self, spec) -> float:
        """Length of a break of this kind, in seconds, for this session's tempo."""
        mean, lo, hi = spec
        return lognormal_with_mean(mean * self.break_length_tempo, _BREAK_LENGTH_CV, lo, hi)
    
    def get_fatigue_multiplier(self) -> float:
        """Multiplier based on the session duration.
        The longer the session runs, the longer the delays."""
        minutes_elapsed = (time.time() - self.session_start) / 60
        # Après 30 min: x1.3, après 60 min: x1.6
        return 1.0 + (minutes_elapsed / 60) * 0.6
    
    def should_take_break(self) -> Tuple[bool, str, float]:
        """Is a break needed?
        Returns: (should_break, break_type, duration)
        
        Breaks are based on REAL interactions, not on profile visits or scrolls.
        
        Both kinds count from the LAST break of either kind, and a short break always comes
        due before the long one can (spacing bounds 4-28 against 30-160): as before, the long
        break never fires. Kept as it is on purpose -- firing it would add minutes of pause to
        every run.
        """
        interactions_since_break = self.interactions_count - self.last_break_at
        
        # Long break, every few dozen interactions
        if interactions_since_break >= self.interactions_before_long_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_long_break = self._break_every(_LONG_BREAK_EVERY, scaled=False)
            return (True, 'long', self._break_length(_LONG_BREAK_S))
        
        # Short break, every several interactions
        if interactions_since_break >= self.interactions_before_short_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_short_break = self._break_every(_SHORT_BREAK_EVERY)
            return (True, 'short', self._break_length(_SHORT_BREAK_S))
        
        return (False, None, 0)
    
    def record_action(self):
        """Record a performed action, for the fatigue computation."""
        self.actions_count += 1
        self.last_action_time = time.time()
    
    def record_interaction(self):
        """Record a real interaction.
        That counter is what triggers the breaks."""
        self.interactions_count += 1
        self.last_action_time = time.time()
    
    def gaussian_delay(self, base_min: float, base_max: float) -> float:
        """A human delay around the middle of [base_min, base_max], fatigue applied.

        Log-normal rather than gaussian: right-skewed like real reaction times, and half again as
        spread as the gaussian it replaces, with the SAME mean. It stays within
        [0.8 x base_min, 1.2 x base_max] by drawing again, never by landing on a bound.
        """
        mean = (base_min + base_max) / 2
        spread = base_max - base_min
        if mean <= 0 or spread <= 0:
            delay = mean
        else:
            cv = _DELAY_SPREAD_GAIN * spread / (2 * (base_max + base_min))
            delay = lognormal_with_mean(mean, cv, base_min * 0.8, base_max * 1.2)
        
        # Appliquer le multiplicateur de fatigue (capped at x1.5 to avoid excessive delays)
        fatigue = min(self.get_fatigue_multiplier(), 1.5)
        delay *= fatigue
        
        return delay
    
    def get_random_offset(self, variance: int = 15) -> Tuple[int, int]:
        """Random coordinate offset, reproducing the imprecision of a finger."""
        return (
            random.randint(-variance, variance),
            random.randint(-variance, variance)
        )
