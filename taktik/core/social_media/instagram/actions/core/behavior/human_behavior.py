"""Human behavior simulation — fatigue, breaks, gaussian delays, random offsets."""

import time
import random
from typing import Tuple


class HumanBehavior:
    """Simule un comportement humain réaliste pour éviter la détection."""
    
    # Singleton pour partager l'état entre toutes les actions
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
        self.actions_count = 0  # Toutes les actions (pour fatigue)
        self.interactions_count = 0  # Seulement les vraies interactions (like, follow, comment)
        self.last_action_time = time.time()
        self.last_break_at = 0
        
        # Configuration des pauses (basées sur les VRAIES interactions uniquement)
        self.interactions_before_short_break = random.randint(8, 15)
        self.interactions_before_long_break = random.randint(30, 50)
        
    def reset_session(self):
        """Reset pour une nouvelle session."""
        self.session_start = time.time()
        self.actions_count = 0
        self.interactions_count = 0
        self.last_action_time = time.time()
        self.last_break_at = 0
        self.interactions_before_short_break = random.randint(8, 15)
        self.interactions_before_long_break = random.randint(30, 50)
    
    def get_fatigue_multiplier(self) -> float:
        """Retourne un multiplicateur basé sur la durée de session.
        Plus la session dure, plus les delays augmentent."""
        minutes_elapsed = (time.time() - self.session_start) / 60
        # Après 30 min: x1.3, après 60 min: x1.6
        return 1.0 + (minutes_elapsed / 60) * 0.6
    
    def should_take_break(self) -> Tuple[bool, str, float]:
        """Vérifie si une pause est nécessaire.
        Returns: (should_break, break_type, duration)
        
        Les pauses sont basées sur les VRAIES interactions (like, follow, comment)
        pas sur les simples visites de profils ou scrolls.
        """
        interactions_since_break = self.interactions_count - self.last_break_at
        
        # Pause longue (1-3 min) toutes les 30-50 interactions
        if interactions_since_break >= self.interactions_before_long_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_long_break = random.randint(30, 50)
            return (True, 'long', random.uniform(60, 180))  # 1-3 min
        
        # Pause courte (5-15s) toutes les 8-15 interactions
        if interactions_since_break >= self.interactions_before_short_break:
            self.last_break_at = self.interactions_count
            self.interactions_before_short_break = random.randint(8, 15)
            return (True, 'short', random.uniform(5, 15))  # 5-15s
        
        return (False, None, 0)
    
    def record_action(self):
        """Enregistre une action effectuée (pour le calcul de fatigue)."""
        self.actions_count += 1
        self.last_action_time = time.time()
    
    def record_interaction(self):
        """Enregistre une vraie interaction (like, follow, comment, story view).
        C'est ce compteur qui déclenche les pauses."""
        self.interactions_count += 1
        self.last_action_time = time.time()
    
    def gaussian_delay(self, base_min: float, base_max: float) -> float:
        """Génère un délai avec distribution gaussienne (plus naturel)."""
        mean = (base_min + base_max) / 2
        std = (base_max - base_min) / 4
        
        # Distribution gaussienne
        delay = random.gauss(mean, std)
        
        # Clamp entre min et max avec une petite marge
        delay = max(base_min * 0.8, min(base_max * 1.2, delay))
        
        # Appliquer le multiplicateur de fatigue (capped at x1.5 to avoid excessive delays)
        fatigue = min(self.get_fatigue_multiplier(), 1.5)
        delay *= fatigue
        
        return delay
    
    def get_random_offset(self, variance: int = 15) -> Tuple[int, int]:
        """Retourne un offset aléatoire pour les coordonnées (simule imprécision du doigt)."""
        return (
            random.randint(-variance, variance),
            random.randint(-variance, variance)
        )
