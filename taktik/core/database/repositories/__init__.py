"""
Repository Pattern - Database Access Layer
Provides clean separation of database operations by domain
"""

from ._base import BaseRepository
from ._factory import get_repository
from .messaging import SentDMRepository
from .instagram import (
    AccountRepository,
    ProfileRepository,
    InteractionRepository,
    SessionRepository,
    ScrapedProfileRepository,
    SocialGraphRepository,
    StatsRepository,
)
from .tiktok import TikTokRepository

__all__ = [
    'BaseRepository',
    'get_repository',
    'SentDMRepository',
    'AccountRepository',
    'ProfileRepository',
    'InteractionRepository',
    'SessionRepository',
    'ScrapedProfileRepository',
    'SocialGraphRepository',
    'StatsRepository',
    'TikTokRepository',
]
