"""
Module d'authentification Instagram.

Sub-packages:
- login/    — Processus de connexion (écran, credentials, résultat, popups)
- signup/   — Processus de création de compte (accueil, téléphone, email)
- session/  — Persistance des sessions (save/load/delete/cleanup)
"""

from .login import InstagramLogin
from .login.models import LoginResult
from .logout import InstagramLogout
from .logout.models import LogoutResult
from .signup import InstagramSignup
from .signup.models import SignupResult
from .session import SessionManager

__all__ = [
    'InstagramLogin',
    'LoginResult',
    'InstagramLogout',
    'LogoutResult',
    'InstagramSignup',
    'SignupResult',
    'SessionManager'
]
