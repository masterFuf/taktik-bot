"""Instagram repositories — data access layer for Instagram tables."""

from .account import AccountRepository
from .profile import ProfileRepository
from .interaction import InteractionRepository
from .session import SessionRepository
from .discovery import DiscoveryRepository

__all__ = [
    'AccountRepository',
    'ProfileRepository',
    'InteractionRepository',
    'SessionRepository',
    'DiscoveryRepository',
]
