"""
TikTok Action Utilities

Re-exports shared ActionUtils/parse_count and adds TikTok-specific overrides.
TikTok usernames: 2-24 characters.
"""

from taktik.core.shared.utils.action_utils import ActionUtils as _SharedActionUtils, parse_count


class ActionUtils(_SharedActionUtils):
    """TikTok-specific ActionUtils.
    
    Inherits all shared utilities. Overrides:
    - is_valid_username: uses TikTok limits (2-24 chars)
    """
    
    @staticmethod
    def is_valid_username(username: str, min_length: int = 2, max_length: int = 24) -> bool:
        """Validate TikTok username format (2-24 characters)."""
        return _SharedActionUtils.is_valid_username(username, min_length=2, max_length=24)
