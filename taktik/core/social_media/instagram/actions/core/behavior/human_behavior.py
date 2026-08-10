"""Human behavior simulation — fatigue, breaks, gaussian delays, random offsets."""

import time
import random
from typing import Tuple


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
        
        self.session_start = time.time()
        self.actions_count = 0  # Every action, for the fatigue
        self.interactions_count = 0  # Real interactions only
        self.last_action_time = time.time()
        self.last_break_at = 0
        
        # Break configuration, based on the REAL interactions only
        self.interactions_before_short_break = random.randint(8, 15)
        self.interactions_before_long_break = random.randint(30, 50)
        
    def reset_session(self):
        """Reset for a new session."""
        self.session_start = time.time()
        self.actions_count = 0
        self.interactions_count = 0
        self.last_action_time = time.time()
        self.last_break_at = 0
        self.interactions_before_short_break = random.randint(8, 15)
        self.interactions_before_long_break = random.randint(30, 50)
    
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
        
        """
        interactions_since_break = self.interactions_count - self.last_break_at
        
        # Long break, every few dozen interactions
        if interactions_since_break >= self.interactions_before_long_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_long_break = random.randint(30, 50)
            return (True, 'long', random.uniform(60, 180))  # 1-3 min
        
        # Short break, every several interactions
        if interactions_since_break >= self.interactions_before_short_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_short_break = random.randint(8, 15)
            return (True, 'short', random.uniform(5, 15))  # 5-15s
        
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
        """Generate a delay on a gaussian distribution, which reads more naturally."""
        mean = (base_min + base_max) / 2
        std = (base_max - base_min) / 4
        
        # Distribution gaussienne
        delay = random.gauss(mean, std)
        
        # Clamp between the bounds, with a small margin
        delay = max(base_min * 0.8, min(base_max * 1.2, delay))
        
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
