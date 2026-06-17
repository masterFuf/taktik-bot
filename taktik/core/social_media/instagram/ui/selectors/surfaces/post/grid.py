from dataclasses import dataclass, field
from typing import List

from ...locales import L
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

    @property
    def next_post_button_selectors(self) -> List[str]:
        return L("post_grid.next_post_button_selectors")

    _back_button_selectors_base: List[str] = field(
        default_factory=lambda: [
            '//android.widget.ImageView[@resource-id="com.instagram.android:id/action_bar_button_back"]',
        ]
    )

    @property
    def back_button_selectors(self) -> List[str]:
        return self._back_button_selectors_base + L("post_grid.back_button_selectors")

    photo_imageview_selector: str = POST_SELECTORS.photo_imageview_selector


POST_GRID_SELECTORS = PostGridSelectors()

