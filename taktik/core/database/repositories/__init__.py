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
    PostAnalysisRepository,
    PostedCommentRepository,
    SessionRepository,
    ScrapedProfileRepository,
    SocialGraphRepository,
    StatsRepository,
)
from .restrictions import AccountRestrictionRepository
from .tiktok import TikTokRepository

__all__ = [
    'BaseRepository',
    'get_repository',
    'SentDMRepository',
    'AccountRestrictionRepository',
    'AccountRepository',
    'ProfileRepository',
    'InteractionRepository',
    'PostAnalysisRepository',
    'PostedCommentRepository',
    'SessionRepository',
    'ScrapedProfileRepository',
    'SocialGraphRepository',
    'StatsRepository',
    'TikTokRepository',
]
