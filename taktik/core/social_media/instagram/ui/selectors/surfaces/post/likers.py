from dataclasses import dataclass, field
from typing import List

from .detail import POST_SELECTORS


@dataclass
class PostLikersSelectors:
    """Selectors dedicated to likes counters and likers entry points."""

    like_count: str = POST_SELECTORS.like_count
    like_count_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.like_count_selectors)
    )
    button_like_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.button_like_selectors)
    )
    photo_like_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.photo_like_selectors)
    )
    automation_like_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.automation_like_indicators)
    )
    automation_like_count_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.automation_like_count_selectors)
    )
    heart_icon_selector: str = POST_SELECTORS.heart_icon_selector
    like_button_advanced_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.like_button_advanced_selectors)
    )
    liked_by_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.liked_by_selectors)
    )
    post_likes_count_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.post_likes_count_selectors)
    )
    like_count_button_selector: str = POST_SELECTORS.like_count_button_selector
    likes_count_click_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.likes_count_click_selectors)
    )


POST_LIKERS_SELECTORS = PostLikersSelectors()

