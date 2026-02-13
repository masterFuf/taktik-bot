"""
Module d'authentification Instagram.

Sub-packages:
- login/    — Processus de connexion (écran, credentials, résultat, popups)
- session/  — Persistance des sessions (save/load/delete/cleanup)
"""

from .login import InstagramLogin
from .login.models import LoginResult
from .session import SessionManager

__all__ = [
    'InstagramLogin',
    'LoginResult',
    'SessionManager'
]
