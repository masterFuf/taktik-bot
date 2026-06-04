"""Instagram repositories — data access layer for Instagram tables."""

from .account import AccountRepository
from .profile import ProfileRepository
from .interaction import InteractionRepository
from .session import SessionRepository
from .scraping import ScrapedProfileRepository
from .social_graph import SocialGraphRepository
from .stats import StatsRepository

__all__ = [
    'AccountRepository',
    'ProfileRepository',
    'InteractionRepository',
    'SessionRepository',
    'ScrapedProfileRepository',
    'SocialGraphRepository',
    'StatsRepository',
]
