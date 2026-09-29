"""
Module d'authentification Instagram.

Sub-packages:
- login/    — login process (screen, credentials, result, popups)
- signup/   — account creation process (welcome, phone, email)
- session/  — session persistence (save, load, delete, cleanup)
"""

from taktik.core.social_media.instagram.auth.login import InstagramLogin
from taktik.core.social_media.instagram.auth.login.models import LoginResult
from taktik.core.social_media.instagram.auth.logout import InstagramLogout
from taktik.core.social_media.instagram.auth.logout.models import LogoutResult
from taktik.core.social_media.instagram.auth.signup import InstagramSignup
from taktik.core.social_media.instagram.auth.signup.models import SignupResult
from taktik.core.social_media.instagram.auth.session import SessionManager

__all__ = [
    'InstagramLogin',
    'LoginResult',
    'InstagramLogout',
    'LogoutResult',
    'InstagramSignup',
    'SignupResult',
    'SessionManager'
]
