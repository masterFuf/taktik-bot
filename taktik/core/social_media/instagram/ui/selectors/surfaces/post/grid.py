from dataclasses import dataclass, field
from typing import List

from .detail import POST_SELECTORS


@dataclass
class PostGridSelectors:
    """Selectors dedicated to grids and post-entry surfaces."""

    post_container: str = POST_SELECTORS.post_container
    post_image: str = POST_SELECTORS.post_image
    post_video: str = POST_SELECTORS.post_video
    carousel_indicator: str = POST_SELECTORS.carousel_indicator
    first_post_grid: str = POST_SELECTORS.first_post_grid
    hashtag_post_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.hashtag_post_selectors)
    )
    carousel_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.carousel_indicators)
    )
    next_post_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.next_post_button_selectors)
    )
    back_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.back_button_selectors)
    )
    photo_imageview_selector: str = POST_SELECTORS.photo_imageview_selector


POST_GRID_SELECTORS = PostGridSelectors()

