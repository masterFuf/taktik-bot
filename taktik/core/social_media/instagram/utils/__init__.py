"""
Utilitaires pour le module Instagram.

Sub-packages:
- filtering/   — Filtrage de profils (critères dynamiques + presets)
- media/       — Capture d'écran / debug visuel
- input/       — Validation entrées + clavier Taktik
- log_config   — Configuration logging
- helpers      — Fonctions utilitaires (random_delay, format_duration)
"""

from .log_config import setup_logger
from .helpers import random_delay, format_duration
from .input.validators import (
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
