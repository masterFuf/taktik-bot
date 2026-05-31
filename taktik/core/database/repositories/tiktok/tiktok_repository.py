"""Public facade for TikTok SQLite repositories."""

from .._base.base_repository import BaseRepository
from .account import TikTokAccountRepositoryMixin
from .filtering import TikTokFilteredProfileRepositoryMixin
from .interaction import TikTokInteractionRepositoryMixin
from .profile import TikTokProfileRepositoryMixin
from .session import TikTokSessionRepositoryMixin
from .stats import TikTokStatsRepositoryMixin


class TikTokRepository(
    TikTokAccountRepositoryMixin,
    TikTokProfileRepositoryMixin,
    TikTokFilteredProfileRepositoryMixin,
    TikTokInteractionRepositoryMixin,
    TikTokStatsRepositoryMixin,
    TikTokSessionRepositoryMixin,
    BaseRepository,
):
    """Stable facade for TikTok persistence domains."""
