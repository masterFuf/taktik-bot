"""
Instagram auth — signup sub-package.
"""

from taktik.core.social_media.instagram.actions.account.signup.signup import InstagramSignup
from taktik.core.social_media.instagram.actions.account.signup.models import SignupResult

__all__ = ['InstagramSignup', 'SignupResult']
