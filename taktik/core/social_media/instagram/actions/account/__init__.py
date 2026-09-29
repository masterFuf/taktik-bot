"""
Module d'authentification Instagram.

Sub-packages:
- login/    — login process (screen, credentials, result, popups)
- signup/   — account creation process (welcome, phone, email)
- session/  — session persistence (save, load, delete, cleanup)
"""

from taktik.core.social_media.instagram.actions.account.login import InstagramLogin
from taktik.core.social_media.instagram.actions.account.login.models import LoginResult
from taktik.core.social_media.instagram.actions.account.logout import InstagramLogout
from taktik.core.social_media.instagram.actions.account.logout.models import LogoutResult
from taktik.core.social_media.instagram.actions.account.signup import InstagramSignup
from taktik.core.social_media.instagram.actions.account.signup.models import SignupResult
from taktik.core.social_media.instagram.actions.account.session import SessionManager

__all__ = [
    'InstagramLogin',
    'LoginResult',
    'InstagramLogout',
    'LogoutResult',
    'InstagramSignup',
    'SignupResult',
    'SessionManager'
]
