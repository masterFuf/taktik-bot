"""
Module d'authentification Instagram.

Ce module gère toutes les opérations d'authentification :
- Login classique (username/password)
- 2FA (SMS, Authenticator)
- Gestion des sessions
- Détection et gestion des erreurs de connexion
"""

from .login import InstagramLogin
from .session_manager import SessionManager

__all__ = [
    'InstagramLogin',
    'SessionManager'
]
