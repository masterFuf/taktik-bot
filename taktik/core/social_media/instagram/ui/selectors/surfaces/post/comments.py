from dataclasses import dataclass, field
from typing import List

from .detail import POST_SELECTORS


@dataclass
class PostCommentsSelectors:
    """Selectors dedicated to the post comments surface."""

    comment_count: str = POST_SELECTORS.comment_count
    comment_button_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_button_indicators)
    )
    photo_comment_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.photo_comment_selectors)
    )
    comment_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_button_selectors)
    )
    comment_field_selector: str = POST_SELECTORS.comment_field_selector
    comment_field_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_field_selectors)
    )
    post_comment_button_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.post_comment_button_selectors)
    )
    comments_list_resource_id: str = POST_SELECTORS.comments_list_resource_id
    comment_username_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comment_username_selectors)
    )
    comments_view_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comments_view_indicators)
    )
    comment_sort_button: str = POST_SELECTORS.comment_sort_button
    expand_replies_selector: str = POST_SELECTORS.expand_replies_selector
    post_comments_count_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.post_comments_count_selectors)
    )


POST_COMMENTS_SELECTORS = PostCommentsSelectors()

