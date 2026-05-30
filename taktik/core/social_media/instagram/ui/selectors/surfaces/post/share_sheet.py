from dataclasses import dataclass, field
from typing import List

from .detail import POST_SELECTORS


@dataclass
class PostShareSheetSelectors:
    """Selectors dedicated to the post share sheet and URL extraction."""

    share_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.share_button_selectors)
    )
    copy_link_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.copy_link_selectors)
    )
    share_picker_url_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.share_picker_url_selectors)
    )
    share_sheet_dimmer: str = POST_SELECTORS.share_sheet_dimmer
    send_post_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.send_post_button_selectors)
    )


POST_SHARE_SHEET_SELECTORS = PostShareSheetSelectors()

