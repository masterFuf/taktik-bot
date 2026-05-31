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
    commenter_button_nodes_selector: str = POST_SELECTORS.all_button_nodes_selector
    comments_view_indicators: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.comments_view_indicators)
    )
    comment_text_nodes_selector: str = (
        '//android.widget.TextView[contains(@resource-id, "row_comment_textview_comment") or '
        'contains(@resource-id, "comment_text")]'
    )
    comment_empty_state_view: str = '//*[@resource-id="com.instagram.android:id/comment_empty_state_view"]'
    comment_title_defocus: str = (
        '//*[contains(@resource-id, "title_text_view")]'
        '[@text="Comments" or @text="Commentaires"]'
    )
    comment_drag_handle_frame: str = '//*[contains(@resource-id, "bottom_sheet_drag_handle_frame")]'
    ime_nav_back_button: str = '//*[@resource-id="android:id/input_method_nav_back"]'
    comment_sort_button: str = POST_SELECTORS.comment_sort_button
    expand_replies_selector: str = POST_SELECTORS.expand_replies_selector
    post_comments_count_selectors: List[str] = field(
        default_factory=lambda: list(POST_SELECTORS.post_comments_count_selectors)
    )

    def comments_list_selector(self) -> str:
        """Return the comments list selector from the catalog-owned resource id."""
        return f'//*[@resource-id="{self.comments_list_resource_id}"]'

    def sort_option_by_content_description(self, label: str) -> str:
        """Return the context-menu option selector for a visible sort label."""
        return f'//*[@content-desc="{label}"]'


POST_COMMENTS_SELECTORS = PostCommentsSelectors()
