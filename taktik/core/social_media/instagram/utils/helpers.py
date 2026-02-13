"""Utility helper functions for the Instagram module."""

import time
import random


def random_delay(min_seconds: float, max_seconds: float = None) -> None:
    """
    Attend un délai aléatoire entre min_seconds et max_seconds.
    Si max_seconds n'est pas fourni, utilise min_seconds comme valeur fixe.
    """
    if max_seconds is None:
        max_seconds = min_seconds
    delay = random.uniform(min_seconds, max_seconds)
    time.sleep(delay)


def format_duration(seconds: float) -> str:
    """
    Formate une durée en secondes en une chaîne lisible.
    Exemple: 3661 -> "1h 1m 1s"
    """
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0 or hours > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    
    return " ".join(parts)
