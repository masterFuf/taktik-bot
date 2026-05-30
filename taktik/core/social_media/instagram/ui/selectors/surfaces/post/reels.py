from dataclasses import dataclass, field
from typing import List

from .detail import POST_SELECTORS


@dataclass
class PostReelsSelectors:
    """Selectors dedicated to reel-specific post surfaces."""

    reels_player: str = POST_SELECTORS.reels_player
    reel_like_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_like_selectors)
    )
    reel_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_indicators)
    )
    automation_reel_specific_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.automation_reel_specific_indicators)
    )
    video_controls: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.video_controls)
    )
    reel_author_username_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_author_username_selectors)
    )
    reel_caption_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_caption_selectors)
    )
    reel_date_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_date_selectors)
    )
    reel_indicators_like_business: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_indicators_like_business)
    )
    reel_player_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.reel_player_indicators)
    )


POST_REELS_SELECTORS = PostReelsSelectors()

