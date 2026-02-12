"""
Instagram Action Utilities

Re-exports shared ActionUtils and adds Instagram-specific overrides.
Instagram usernames: 1-30 characters.
"""

from taktik.core.shared.utils.action_utils import ActionUtils as _SharedActionUtils
from typing import Optional


class ActionUtils(_SharedActionUtils):
    """Instagram-specific ActionUtils.
    
    Inherits all shared utilities. Overrides:
    - parse_number_from_text: delegates to Instagram's centralized parser
    - is_valid_username: uses Instagram limits (1-30 chars)
    """
    
    @staticmethod
    def parse_number_from_text(text: str) -> Optional[int]:
        """Parse number from text - delegates to Instagram's centralized parser."""
        from ...ui.extractors import parse_number_from_text as central_parser
        result = central_parser(text)
        return result if result > 0 else None
    
    @staticmethod
    def is_valid_username(username: str, min_length: int = 1, max_length: int = 30) -> bool:
        """Validate Instagram username format (1-30 characters)."""
        return _SharedActionUtils.is_valid_username(username, min_length=1, max_length=30)
