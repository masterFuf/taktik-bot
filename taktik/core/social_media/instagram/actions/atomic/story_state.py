"""Small, locale-aware helpers for observable story viewer state."""

import re
from typing import Optional


_STORY_POSITION_PATTERN = re.compile(
    r"\b(?:story\s+)?(\d+)\s+(?:of|sur)\s+(\d+)\b",
    re.IGNORECASE,
)


def parse_story_position(value: str) -> Optional[tuple[int, int]]:
    """Extract an EN/FR ``current / total`` position from a viewer description."""
    match = _STORY_POSITION_PATTERN.search(value or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))
