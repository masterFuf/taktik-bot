"""
Utilitaires pour le module Instagram.

Ce package contient des fonctions utilitaires pour le module Instagram,
telles que la gestion des logs, des captures d'écran, et la validation des entrées.
"""

import os
import time
import random
import logging
from typing import Optional, Dict, Any, List, Tuple, Union
from pathlib import Path

# Import des utilitaires
from .logger import setup_logger
from .validators import (
    validate_username,
    validate_hashtag,
    validate_url,
    validate_post_id
)

__all__ = [
    'setup_logger',
    'validate_username',
    'validate_hashtag',
    'validate_url',
    'validate_post_id',
    'random_delay',
    'format_duration'
]

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
