"""
Repository Pattern - Database Access Layer
Provides clean separation of database operations by domain
"""

from ._base import BaseRepository
from .instagram import AccountRepository, ProfileRepository, InteractionRepository, SessionRepository, DiscoveryRepository
from .tiktok import TikTokRepository

__all__ = [
    'BaseRepository',
    'AccountRepository',
    'ProfileRepository',
    'InteractionRepository',
    'SessionRepository',
    'DiscoveryRepository',
    'TikTokRepository',
]
